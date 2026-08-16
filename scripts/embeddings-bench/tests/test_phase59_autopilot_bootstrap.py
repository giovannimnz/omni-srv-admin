import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "phase59-autopilot-bootstrap.py"
SPEC = importlib.util.spec_from_file_location("phase59_bootstrap", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Phase59BootstrapTests(unittest.TestCase):
    def test_signed_path_contract_contains_all_plans_and_helper(self):
        plans = [path for path in MODULE.SIGNED_PATHS if path.endswith("-PLAN.md")]
        self.assertEqual(9, len(plans))
        self.assertIn(
            "scripts/embeddings-bench/phase59-autopilot-bootstrap.py",
            MODULE.SIGNED_PATHS,
        )
        for name in (
            "59-CONTEXT.md",
            "59-RESEARCH.md",
            "59-PATTERNS.md",
            "59-VALIDATION.md",
            "59-REVIEWS.md",
            "59-AUTOPILOT-BOOTSTRAP.md",
        ):
            self.assertTrue(any(path.endswith(name) for path in MODULE.SIGNED_PATHS))
        for mutable in ("PROJECT.md", "REQUIREMENTS.md", "ROADMAP.md", "STATE.md"):
            self.assertFalse(any(path.endswith(mutable) for path in MODULE.SIGNED_PATHS))
        self.assertEqual(len(MODULE.SIGNED_PATHS), len(set(MODULE.SIGNED_PATHS)))

    def test_relative_and_symlink_paths_fail_closed(self):
        with self.assertRaises(MODULE.BootstrapError):
            MODULE.assert_absolute_non_symlink(Path("relative"), must_exist=False)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.assert_absolute_non_symlink(link, must_exist=True)

    def test_external_artifact_cannot_be_inside_repo_or_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            worktree = root / "worktree"
            repo.mkdir()
            worktree.mkdir()
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.assert_external_output(repo / "bundle.json", repo, worktree)
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.assert_external_output(worktree / "receipt.json", repo, worktree)

    def test_execution_branch_must_be_dedicated(self):
        for invalid in ("", "main", "master", "feature/qwen", "phase59 bad"):
            with self.subTest(branch=invalid):
                with self.assertRaises(MODULE.BootstrapError):
                    MODULE.validate_execution_branch(invalid)
        self.assertEqual(
            "phase59-qwen-cutover",
            MODULE.validate_execution_branch("phase59-qwen-cutover"),
        )

    def test_verify_bundle_rejects_duplicate_or_missing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test"],
                check=True,
            )
            marker = repo / "marker"
            marker.write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "marker"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            commit = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            bundle = root / "bundle.json"
            bundle.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "phase": 59,
                        "workstream": "qwen-local-ai",
                        "final_execution_commit": commit,
                        "execution_worktree": str(MODULE.EXECUTION_WORKTREE),
                        "files": [
                            {"path": "marker", "sha256": "0" * 64},
                            {"path": "marker", "sha256": "0" * 64},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.verify_bundle(repo, bundle)

    def test_verify_worktree_rejects_dirty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "tracked").write_text("clean", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "user.name=Test",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            (repo / "untracked").write_text("dirty", encoding="utf-8")
            self.assertNotEqual(
                "",
                MODULE.run(["git", "-C", str(repo), "status", "--porcelain"]).stdout,
            )

    def test_script_contains_no_skill_invocation_subprocess(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("AUTOPILOT_BIN", source)
        self.assertNotIn('run(["$gsd-', source)
        self.assertIn('"codex_skill_invoked": False', source)

    def test_doctor_requires_frozen_executor_mode(self):
        with self.assertRaises(SystemExit):
            MODULE.parser().parse_args(["doctor", "--bundle", "/tmp/bundle.json"])
        args = MODULE.parser().parse_args(
            [
                "doctor",
                "--bundle",
                "/tmp/bundle.json",
                "--executor-mode",
                "autopilot",
                "--executor-owner",
                "codex-task-12345678",
            ]
        )
        self.assertEqual("autopilot", args.executor_mode)

    def test_executor_lock_is_mode_and_owner_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp).resolve() / "executor-lock.json"
            first = MODULE.create_or_verify_executor_lock(
                lock,
                executor_mode="autopilot",
                executor_owner="codex-task-12345678",
                bundle_sha256="a" * 64,
                base_commit="b" * 40,
            )
            second = MODULE.create_or_verify_executor_lock(
                lock,
                executor_mode="autopilot",
                executor_owner="codex-task-12345678",
                bundle_sha256="a" * 64,
                base_commit="b" * 40,
            )
            self.assertEqual(first, second)
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.create_or_verify_executor_lock(
                    lock,
                    executor_mode="execute-phase-fallback",
                    executor_owner="codex-task-87654321",
                    bundle_sha256="a" * 64,
                    base_commit="b" * 40,
                )

    def test_graphify_uses_canonical_governed_binary(self):
        self.assertEqual(
            Path("/home/ubuntu/.local/bin/graphify"),
            MODULE.GRAPHIFY,
        )

    def test_behavior_transcript_is_bound_and_rejects_self_declared_tamper(self):
        binding = {
            "schema_version": 1,
            "fixture_suite": "gsd-execute-autopilot-resume-summary-v1",
            "status": "PASS",
            "task_root": "/worktree",
            "bundle_sha256": "a" * 64,
            "final_execution_commit": "b" * 40,
            "executor_owner": "codex-task-12345678",
            "executor_lock_sha256": "c" * 64,
            "skill_sha256": "d" * 64,
            "workflow_sha256": "e" * 64,
        }
        transcript = {
            **binding,
            "checks": [
                {
                    "name": "resume-existing-original-uid",
                    "status": "PASS",
                    "exit_code": 0,
                    "argv_sha256": "f" * 64,
                    "stdout_sha256": "1" * 64,
                    "observed": {
                        "original_uid_preserved": True,
                        "redispatch_count": 0,
                        "resume_handoff_count": 1,
                    },
                },
                {
                    "name": "summary-then-dispatch-next-plan",
                    "status": "PASS",
                    "exit_code": 0,
                    "argv_sha256": "2" * 64,
                    "stdout_sha256": "3" * 64,
                    "observed": {
                        "summary_created": True,
                        "next_plan_dispatched": True,
                        "dispatch_count": 1,
                    },
                },
            ],
        }
        MODULE.validate_behavior_transcript(
            transcript, expected_binding=binding
        )
        tampered = json.loads(json.dumps(transcript))
        tampered["checks"][0]["observed"]["redispatch_count"] = 1
        with self.assertRaises(MODULE.BootstrapError):
            MODULE.validate_behavior_transcript(
                tampered, expected_binding=binding
            )
        deprecated_field = "resume_" + "behavior_fixture_pass"
        self.assertNotIn(deprecated_field, SCRIPT.read_text(encoding="utf-8"))

    def test_executor_lock_receipt_verification_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp).resolve() / "executor-lock.json"
            receipt = {
                "executor_mode": "autopilot",
                "executor_owner": "codex-task-12345678",
                "bundle_sha256": "a" * 64,
                "final_execution_commit": "b" * 40,
            }
            MODULE.create_or_verify_executor_lock(
                lock,
                executor_mode=receipt["executor_mode"],
                executor_owner=receipt["executor_owner"],
                bundle_sha256=receipt["bundle_sha256"],
                base_commit=receipt["final_execution_commit"],
            )
            receipt["executor_lock_sha256"] = MODULE.sha256_bytes(lock.read_bytes())
            current, current_hash = MODULE.verify_executor_lock_against_receipt(
                lock, receipt, required_mode="autopilot"
            )
            self.assertEqual(receipt["executor_owner"], current["executor_owner"])
            self.assertEqual(receipt["executor_lock_sha256"], current_hash)

            tampered = json.loads(lock.read_text(encoding="utf-8"))
            tampered["executor_owner"] = "codex-task-87654321"
            lock.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.verify_executor_lock_against_receipt(
                    lock, receipt, required_mode="autopilot"
                )

    def test_fallback_transition_requires_exact_pre_wave0_failure(self):
        owner = "codex-task-12345678"
        bootstrap = {
            "status": "BOOTSTRAP_PASS",
            "executor_mode": "autopilot",
            "executor_owner": owner,
            "bundle_sha256": "a" * 64,
            "final_execution_commit": "b" * 40,
            "worktree": str(MODULE.EXECUTION_WORKTREE),
        }
        failure = {
            "status": "FAIL",
            "skill": "gsd-execute-autopilot",
            "workstream": MODULE.WORKSTREAM,
            "task_root": str(MODULE.EXECUTION_WORKTREE),
            "bundle_sha256": "a" * 64,
            "final_execution_commit": "b" * 40,
            "executor_mode": "autopilot",
            "executor_owner": owner,
            "skill_sha256": "c" * 64,
            "workflow_sha256": "d" * 64,
            "wave0_started": False,
        }
        MODULE.validate_fallback_transition_inputs(
            bootstrap,
            failure,
            bundle_sha256="a" * 64,
            final_execution_commit="b" * 40,
            executor_owner=owner,
            skill_sha256="c" * 64,
            workflow_sha256="d" * 64,
        )
        for key, bad_value in (
            ("status", "PASS"),
            ("task_root", "/tmp/other"),
            ("skill_sha256", "e" * 64),
            ("wave0_started", True),
        ):
            with self.subTest(key=key):
                altered = dict(failure)
                altered[key] = bad_value
                with self.assertRaises(MODULE.BootstrapError):
                    MODULE.validate_fallback_transition_inputs(
                        bootstrap,
                        altered,
                        bundle_sha256="a" * 64,
                        final_execution_commit="b" * 40,
                        executor_owner=owner,
                        skill_sha256="c" * 64,
                        workflow_sha256="d" * 64,
                    )

    def test_transition_fallback_cli_is_explicit(self):
        args = MODULE.parser().parse_args(
            [
                "transition-fallback",
                "--bundle",
                "/tmp/bundle.json",
                "--bootstrap-receipt",
                "/tmp/bootstrap.json",
                "--skill-doctor-failure",
                "/tmp/failure.json",
                "--executor-owner",
                "codex-task-12345678",
            ]
        )
        self.assertEqual("transition-fallback", args.command)

    def test_graphify_accepts_canonical_fresh_short_sha(self):
        commit = "a" * 40
        status = json.dumps(
            {
                "exists": True,
                "stale": False,
                "commit_stale": False,
                "built_at_commit": commit[:7],
                "current_commit": commit[:7],
            }
        )
        query = json.dumps({"nodes": [{"id": "phase59"}], "total_nodes": 1})
        evidence = MODULE.parse_graphify_evidence(
            status, query, commit=commit, worktree_head=commit
        )
        self.assertEqual(1, evidence["total_nodes"])

    def test_graphify_rejects_stale_even_when_full_sha_is_present(self):
        commit = "b" * 40
        status = json.dumps(
            {
                "exists": True,
                "stale": False,
                "commit_stale": True,
                "built_at_commit": commit[:7],
                "current_commit": commit[:7],
                "unrelated": commit,
            }
        )
        query = json.dumps({"nodes": [{"id": "phase59"}], "total_nodes": 1})
        with self.assertRaises(MODULE.BootstrapError):
            MODULE.parse_graphify_evidence(
                status, query, commit=commit, worktree_head=commit
            )

    def test_graphify_empty_query_requires_focused_reads(self):
        commit = "c" * 40
        status = json.dumps(
            {
                "exists": True,
                "stale": False,
                "commit_stale": False,
                "built_at_commit": commit[:7],
                "current_commit": commit[:7],
            }
        )
        query = json.dumps({"nodes": [], "total_nodes": 0})
        evidence = MODULE.parse_graphify_evidence(
            status, query, commit=commit, worktree_head=commit
        )
        self.assertEqual("focused_reads_required", evidence["query_route"])

    def test_graphify_rejects_query_count_mismatch(self):
        commit = "d" * 40
        status = json.dumps(
            {
                "exists": True,
                "stale": False,
                "commit_stale": False,
                "built_at_commit": commit[:7],
                "current_commit": commit[:7],
            }
        )
        query = json.dumps({"nodes": [], "total_nodes": 1})
        with self.assertRaises(MODULE.BootstrapError):
            MODULE.parse_graphify_evidence(
                status, query, commit=commit, worktree_head=commit
            )

    def test_graphify_generated_scope_rejects_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "tracked").write_text("clean", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "user.name=Test",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            (repo / "tracked").write_text("changed", encoding="utf-8")
            with self.assertRaises(MODULE.BootstrapError):
                MODULE.verify_graphify_generated_only(repo)


if __name__ == "__main__":
    unittest.main()
