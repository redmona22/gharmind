import uuid

from tests.dashboard.helpers import auth, ids, login


def test_salesperson_sees_only_their_own_leads(client, company):
    r = client.get("/leads", headers=auth(login(client, company.sales1)))
    assert r.status_code == 200
    assert ids(r) == {str(company.lead1.contact_id)}
    assert r.json()["total"] == 1


def test_admin_sees_the_whole_company_but_never_another_company(client, company, other_company):
    r = client.get("/leads", headers=auth(login(client, company.admin)))
    mine = {str(l.contact_id) for l in (company.lead1, company.lead2, company.lead3)}
    theirs = {str(l.contact_id) for l in (other_company.lead1, other_company.lead2, other_company.lead3)}
    assert ids(r) == mine
    assert not (ids(r) & theirs)


def test_leads_are_sorted_hottest_first(client, company):
    items = client.get("/leads", headers=auth(login(client, company.admin))).json()["items"]
    scores = [i["lead_score"] for i in items]
    assert scores == sorted(scores, reverse=True) and scores[0] == 80


def test_lead_list_shows_last_message_and_conversation(client, company):
    item = client.get("/leads", headers=auth(login(client, company.sales1))).json()["items"][0]
    assert item["conversation_id"] == str(company.lead1.conversation_id)
    assert item["conversation_status"] == "agent"
    assert item["last_message"]["content"] == "hello from one"


def test_filters(client, company):
    admin = auth(login(client, company.admin))
    hot = client.get("/leads?score_min=50", headers=admin)
    assert ids(hot) == {str(company.lead2.contact_id)}
    unassigned = client.get("/leads?assigned_to=none", headers=admin)
    assert ids(unassigned) == {str(company.lead3.contact_id)}
    by_name = client.get("/leads?q=Lead%20Three", headers=admin)
    assert ids(by_name) == {str(company.lead3.contact_id)}
    assert client.get("/leads?assigned_to=not-a-uuid", headers=admin).status_code == 422


def test_salesperson_cannot_open_someone_elses_lead(client, company):
    token = auth(login(client, company.sales1))
    assert client.get(f"/leads/{company.lead1.contact_id}", headers=token).status_code == 200
    assert client.get(f"/leads/{company.lead2.contact_id}", headers=token).status_code == 404
    assert client.get(f"/leads/{company.lead3.contact_id}", headers=token).status_code == 404  # unassigned
    assert client.get(f"/leads/{uuid.uuid4()}", headers=token).status_code == 404


def test_admin_cannot_open_another_companys_lead(client, company, other_company):
    admin = auth(login(client, company.admin))
    assert client.get(f"/leads/{other_company.lead1.contact_id}", headers=admin).status_code == 404


def test_only_admins_assign_leads(client, company):
    sales = auth(login(client, company.sales1))
    r = client.patch(f"/leads/{company.lead3.contact_id}/assign", headers=sales, json={"user_id": str(company.sales1.id)})
    assert r.status_code == 403

    admin = auth(login(client, company.admin))
    r = client.patch(f"/leads/{company.lead3.contact_id}/assign", headers=admin, json={"user_id": str(company.sales1.id)})
    assert r.status_code == 200
    assert len(client.get("/leads", headers=sales).json()["items"]) == 2  # now sees the new lead

    r = client.patch(f"/leads/{company.lead3.contact_id}/assign", headers=admin, json={"user_id": None})
    assert r.status_code == 200 and r.json()["assigned_user_id"] is None


def test_cannot_assign_a_lead_to_a_user_from_another_company(client, company, other_company):
    admin = auth(login(client, company.admin))
    r = client.patch(f"/leads/{company.lead3.contact_id}/assign", headers=admin,
                     json={"user_id": str(other_company.admin.id)})
    assert r.status_code == 404
