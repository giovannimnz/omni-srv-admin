package simulations;

import static io.gatling.javaapi.core.CoreDsl.*;
import static io.gatling.javaapi.http.HttpDsl.*;

import io.gatling.javaapi.core.*;
import io.gatling.javaapi.http.*;
import java.time.Duration;

/**
 * Gatling 3 Performance Simulation para o Atius SSO e Endpoints Críticos
 * Executado com Java 21 OpenJDK ARM64 na pipeline self-hosted no atius-srv-4.
 */
public class AtiusSsoPerformanceSimulation extends Simulation {

    HttpProtocolBuilder httpProtocol = http
        .baseUrl("https://sso.atius.com.br")
        .acceptHeader("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        .acceptLanguageHeader("pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
        .userAgentHeader("Gatling/PerformanceTest/AtiusPipeline");

    ScenarioBuilder scn = scenario("Atius SSO Login Navigation Simulation")
        .exec(
            http("SSO_Login_Page_Request")
                .get("/login")
                .check(status().is(200))
        )
        .pause(Duration.ofMillis(500))
        .exec(
            http("Keycloak_OIDC_Discovery_Request")
                .get("https://auth.atius.com.br/realms/atius/.well-known/openid-configuration")
                .check(status().is(200))
        );

    {
        setUp(
            scn.injectOpen(
                rampUsers(20).during(Duration.ofSeconds(10)),
                constantUsersPerSec(5).during(Duration.ofSeconds(15))
            )
        ).protocols(httpProtocol)
         .assertions(
             global().responseTime().percentile3().lt(1500), // p95 < 1500ms
             global().successfulRequests().percent().gt(95.0) // Sucesso > 95%
         );
    }
}
