import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.session import get_db, Base
from app.models.models import Tenant, User, PlanName
from app.core.auth import create_access_token

TEST_DB_URL = "postgresql+asyncpg://productsync:password@localhost:5432/productsync_test"


@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db(engine):
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db):
    async def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def tenant(db):
    t = Tenant(
        id=uuid.uuid4(),
        name="Test Tenant",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        plan=PlanName.starter,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def user(db, tenant):
    from app.core.auth import pwd_context
    u = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"test-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=pwd_context.hash("testpass123"),
        full_name="Test User",
        is_owner=True,
        is_active=True,
        email_confirmed=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def auth_headers(user):
    token = create_access_token(user.id, user.tenant_id)
    return {"Authorization": f"Bearer {token}"}
