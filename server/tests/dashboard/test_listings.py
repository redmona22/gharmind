import uuid

from app.agent.tools import ToolContext, execute_tool
from tests.dashboard.helpers import auth, ids, login

SALE = {"listing_type": "sale", "project": "Test Heights", "price": 5_000_000, "bhk": 2,
        "location": "Patia, Bhubaneswar", "rera_number": "RP/TEST/1"}


def agent_sees(company):
    ctx = ToolContext(company.tenant_id, company.lead3.contact_id, company.lead3.conversation_id)
    return {x["project"] for x in execute_tool("search_listings", {}, ctx)["listings"]}


def test_admin_creates_and_lists_listings(client, company):
    admin = auth(login(client, company.admin))
    r = client.post("/listings", headers=admin, json=SALE)
    assert r.status_code == 201 and r.json()["promotable"] is True
    listed = client.get("/listings", headers=admin).json()
    assert listed["total"] == 1 and listed["items"][0]["project"] == "Test Heights"


def test_sale_without_rera_is_flagged_and_hidden_from_the_agent(client, company):
    admin = auth(login(client, company.admin))
    no_rera = {**SALE, "project": "No RERA Towers", "rera_number": None}
    r = client.post("/listings", headers=admin, json=no_rera)
    assert r.status_code == 201 and r.json()["promotable"] is False
    client.post("/listings", headers=admin, json=SALE)
    assert agent_sees(company) == {"Test Heights"}


def test_rentals_do_not_need_a_rera_number(client, company):
    admin = auth(login(client, company.admin))
    r = client.post("/listings", headers=admin, json={
        "listing_type": "rent", "project": "Green Nest", "price": 18_000, "deposit": 90_000, "bhk": 2})
    assert r.status_code == 201 and r.json()["promotable"] is True


def test_salespeople_can_read_but_not_change_listings(client, company):
    admin = auth(login(client, company.admin))
    created = client.post("/listings", headers=admin, json=SALE).json()
    sales = auth(login(client, company.sales1))
    assert client.get("/listings", headers=sales).status_code == 200
    assert client.post("/listings", headers=sales, json=SALE).status_code == 403
    assert client.put(f"/listings/{created['id']}", headers=sales, json=SALE).status_code == 403
    assert client.delete(f"/listings/{created['id']}", headers=sales).status_code == 403


def test_update_and_withdraw(client, company):
    admin = auth(login(client, company.admin))
    lid = client.post("/listings", headers=admin, json=SALE).json()["id"]
    r = client.put(f"/listings/{lid}", headers=admin, json={**SALE, "price": 5_200_000})
    assert r.status_code == 200 and r.json()["price"] == 5_200_000
    assert agent_sees(company) == {"Test Heights"}

    r = client.delete(f"/listings/{lid}", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert agent_sees(company) == set()  # withdrawn listings are never offered


def test_each_company_only_sees_its_own_listings(client, company, other_company):
    a = auth(login(client, company.admin))
    b = auth(login(client, other_company.admin))
    mine = client.post("/listings", headers=a, json=SALE).json()["id"]
    theirs = client.post("/listings", headers=b, json={**SALE, "project": "Their Tower"}).json()["id"]

    assert ids(client.get("/listings", headers=a)) == {mine}
    assert ids(client.get("/listings", headers=b)) == {theirs}
    assert client.put(f"/listings/{theirs}", headers=a, json=SALE).status_code == 404
    assert client.delete(f"/listings/{theirs}", headers=a).status_code == 404
    assert client.put(f"/listings/{uuid.uuid4()}", headers=a, json=SALE).status_code == 404


def test_bad_input_is_rejected(client, company):
    admin = auth(login(client, company.admin))
    assert client.post("/listings", headers=admin, json={**SALE, "price": -5}).status_code == 422
    assert client.post("/listings", headers=admin, json={**SALE, "listing_type": "lease"}).status_code == 422
    assert client.post("/listings", headers=admin, json={**SALE, "project": ""}).status_code == 422
    assert client.post("/listings", headers=admin, json={**SALE, "bhk": 99}).status_code == 422
