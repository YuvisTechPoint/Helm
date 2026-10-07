from fastapi.testclient import TestClient

from acquisition.modules.scoring import compute_scores, fit_from_icp
from acquisition.modules.icp import sample_leads_for_cell
from api.main import create_app
from core.stats import thompson_shares, wilson_lower_bound
from youtube.modules.diagnostician import Funnel, diagnose


def _funnel(**overrides) -> Funnel:
    base = dict(
        age_hours=72,
        views=100,
        channel_median_views=80,
        impressions_ratio=1,
        ctr=0.06,
        retention_first_30=0.5,
        retention_mid=0.5,
        subscribers_per_1000=5,
        low_rpm_traffic_share=0.1,
    )
    base.update(overrides)
    return Funnel(**base)


def test_health_ready_request_id_and_ops():
    client = TestClient(create_app())
    health = client.get("/health")
    assert health.status_code == 200
    assert "X-Request-Id" in health.headers
    assert health.json()["components"]["youtube"]["kill"] is False
    ready = client.get("/ready")
    assert ready.status_code == 200 and ready.json()["ready"] is True
    isolation = client.get("/acquisition/funnel", params={"tenant_id": "someone-else"})
    assert isolation.status_code == 403
    ops = client.get("/acquisition/ops")
    assert ops.status_code == 200 and "volume" in ops.json() and "kill" in ops.json()
    score = client.post(
        "/acquisition/score",
        json={"email": "ada@buyer.example", "first_name": "Ada", "company": "Example", "reason": "checkout abandonment", "industry": "ecommerce"},
    )
    assert score.status_code == 200
    assert "explain" in score.json() and score.json()["reach"] == 1.0
    yt = client.get("/youtube/ops")
    assert yt.status_code == 200 and "quota" in yt.json()
    leads = client.get("/acquisition/leads", params={"limit": 2, "offset": 0})
    assert leads.json()["total"] >= 0 and "items" in leads.json()


def test_wilson_beats_noisy_high_rate_and_thompson_explores():
    noisy = wilson_lower_bound(2, 5)
    solid = wilson_lower_bound(40, 120)
    assert solid > noisy
    shares = thompson_shares([{"successes": 0, "failures": 0}, {"successes": 40, "failures": 2}], __import__("random").Random(3))
    assert abs(sum(shares) - 1) < 1e-9
    assert min(shares) >= 0.07


def test_fit_uses_icp_and_anti_ideal():
    profile = {"anti_ideal_clients": ["enterprise-inc"], "ideal_clients": ["shop"], "geographies": ["india"]}
    icp = {"industry": "ecommerce", "roles": ["Head of Ecommerce"], "geo": "india"}
    fit = fit_from_icp({"industry": "ecommerce", "title": "Head of Ecommerce", "geo": "india", "company": "Shop A"}, icp, profile)
    anti = fit_from_icp({"company": "Enterprise-Inc Ltd", "industry": "ecommerce"}, icp, profile)
    assert fit > 0.7 and anti == 0.1
    scores = compute_scores(
        {"email": "a@b.co", "industry": "ecommerce", "title": "Head of Ecommerce", "intent": 0.7, "company": "Shop"},
        icp,
        profile,
        "valid",
        [{"kind": "performance", "strength": 0.8}],
    )
    assert scores["score"] > 0.3 and scores["explain"]["fit_parts"]["industry"]


def test_icp_leads_are_stamped_and_youtube_diagnosis_has_stats():
    leads = sample_leads_for_cell({"name": "ecom-heads", "industry": "ecommerce", "roles": ["Head of Ecommerce"], "region": "india"})
    assert leads and leads[0]["industry"] == "ecommerce"
    held = diagnose(_funnel(age_hours=24), [])
    assert held["action"] == "hold" and "stats" in held
    packing = diagnose(_funnel(ctr=0.02), [])
    assert packing["action"] == "fix" and packing["stats"]["ctr_posterior"]["mean"] > 0
