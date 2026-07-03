from sibyl.identity.adapters.repository import InstallationRepository

repository = InstallationRepository()


async def test_get_or_create_creates_a_new_installation(db_session):
    installation = await repository.get_or_create_by_github_id(
        db_session, github_installation_id=555111, organization_login="acme"
    )

    assert installation.github_installation_id == 555111
    assert installation.organization_login == "acme"


async def test_get_or_create_is_idempotent(db_session):
    first = await repository.get_or_create_by_github_id(
        db_session, github_installation_id=555222, organization_login="acme"
    )
    second = await repository.get_or_create_by_github_id(
        db_session, github_installation_id=555222, organization_login="acme"
    )

    assert first.id == second.id


async def test_get_by_github_id_returns_none_when_missing(db_session):
    result = await repository.get_by_github_id(db_session, github_installation_id=999999)

    assert result is None
