from app.models.couchdb_changes import CouchDBChanges
from app.repos.last_seq_repo import LastSeqRepo
from tests.conftest import FakeSession


def test_get_last_seq_defaults_to_now():
    session = FakeSession(first_result=None)
    repo = LastSeqRepo(session)

    assert repo.get_last_seq() == "now"
    assert session.queried_model is CouchDBChanges


def test_update_last_seq_inserts_when_missing():
    session = FakeSession(first_result=None)
    repo = LastSeqRepo(session)

    repo.update_last_seq("123")

    # FakeSession stores the added object as .offset
    assert isinstance(session.offset, CouchDBChanges)
    assert session.offset.last_seq == "123"
    assert session.committed is True


def test_update_last_seq_updates_existing():
    session = FakeSession(first_result=CouchDBChanges(last_seq="111"))
    repo = LastSeqRepo(session)

    repo.update_last_seq("222")

    assert session.last_query.first_result.last_seq == "222"
    assert session.committed is True
