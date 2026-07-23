import { createServer } from "node:http";
import { AutoModelForCausalLM, AutoTokenizer, env } from "@huggingface/transformers";

const MODEL_ID = process.env.MODEL_ID || "onnx-community/Qwen3-Reranker-0.6B-ONNX";
const MODEL_DTYPE = process.env.MODEL_DTYPE || "q8";
const MAX_LENGTH = Number(process.env.MAX_LENGTH || 8192);
const MAX_DOCUMENTS = Number(process.env.MAX_DOCUMENTS || 20);
const BATCH_SIZE = Number(process.env.BATCH_SIZE || 4);
const PORT = Number(process.env.PORT || 8080);
const INSTRUCTION = process.env.RERANK_INSTRUCTION ||
  "Given a web search query, retrieve relevant passages that answer the query";

env.cacheDir = process.env.MODEL_CACHE || "/data";
env.allowRemoteModels = true;

const SYSTEM_PROMPT =
  "Judge whether the Document meets the requirements based on the Query and the Instruct provided. " +
  'Note that the answer can only be "yes" or "no".';

let tokenizer;
let model;
let yesToken;
let noToken;
let loadError;
let queue = Promise.resolve();

function buildPrompt(query, document) {
  return `<|im_start|>system\n${SYSTEM_PROMPT}<|im_end|>\n` +
    `<|im_start|>user\n<Instruct>: ${INSTRUCTION}\n\n<Query>: ${query}\n\n` +
    `<Document>: ${document}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n`;
}

function probability(yes, no) {
  const max = Math.max(yes, no);
  const yesExp = Math.exp(yes - max);
  const noExp = Math.exp(no - max);
  return yesExp / (yesExp + noExp);
}

async function scoreBatch(query, documents) {
  const prompts = documents.map((document) => buildPrompt(query, document));
  const inputs = tokenizer(prompts, {
    padding: true,
    truncation: true,
    max_length: MAX_LENGTH,
  });
  const output = await model(inputs);
  const [batch, sequenceLength, vocabulary] = output.logits.dims;
  const scores = [];
  for (let index = 0; index < batch; index += 1) {
    const offset = (index * sequenceLength + sequenceLength - 1) * vocabulary;
    scores.push(probability(output.logits.data[offset + yesToken], output.logits.data[offset + noToken]));
  }
  return scores;
}

async function rerank(query, documents) {
  const results = [];
  for (let offset = 0; offset < documents.length; offset += BATCH_SIZE) {
    const batchDocuments = documents.slice(offset, offset + BATCH_SIZE);
    const scores = await scoreBatch(query, batchDocuments);
    scores.forEach((score, index) => {
      results.push({ index: offset + index, score });
    });
  }
  return results.sort((left, right) => right.score - left.score);
}

async function load() {
  tokenizer = await AutoTokenizer.from_pretrained(MODEL_ID);
  model = await AutoModelForCausalLM.from_pretrained(MODEL_ID, {
    dtype: MODEL_DTYPE,
    device: "cpu",
  });
  yesToken = Number(tokenizer.convert_tokens_to_ids("yes"));
  noToken = Number(tokenizer.convert_tokens_to_ids("no"));
  if (!Number.isInteger(yesToken) || !Number.isInteger(noToken)) {
    throw new Error("Qwen reranker yes/no token IDs could not be resolved");
  }
}

function json(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload),
  });
  response.end(payload);
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > 2_000_000) reject(new Error("payload too large"));
    });
    request.on("end", () => resolve(JSON.parse(body || "{}")));
    request.on("error", reject);
  });
}

const server = createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    return json(response, model ? 200 : 503, { status: model ? "ok" : "loading" });
  }
  if (request.method !== "POST" || !["/rerank", "/v1/rerank"].includes(request.url)) {
    return json(response, 404, { error: "not found" });
  }
  if (!model) return json(response, 503, { error: loadError?.message || "model loading" });
  try {
    const body = await readBody(request);
    const query = typeof body.query === "string" ? body.query : "";
    const documents = Array.isArray(body.texts) ? body.texts : body.documents;
    if (!query || !Array.isArray(documents) || documents.length === 0) {
      return json(response, 400, { error: "query and texts/documents are required" });
    }
    if (documents.length > MAX_DOCUMENTS || documents.some((item) => typeof item !== "string")) {
      return json(response, 400, { error: `maximum ${MAX_DOCUMENTS} string documents` });
    }
    const work = queue.then(() => rerank(query, documents));
    queue = work.catch(() => undefined);
    return json(response, 200, await work);
  } catch (error) {
    return json(response, 400, { error: error instanceof Error ? error.message : "invalid request" });
  }
});

load().catch((error) => {
  loadError = error;
  console.error(error);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(JSON.stringify({ model: MODEL_ID, dtype: MODEL_DTYPE, port: PORT, maxLength: MAX_LENGTH }));
});
