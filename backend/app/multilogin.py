from pydantic import BaseModel


class BrowserSession(BaseModel):
    profile_id: str
    cdp_url: str


class MultiloginClient:
    async def create_session(self, profile_id: str) -> BrowserSession:
        return BrowserSession(profile_id=profile_id, cdp_url=f"ws://multilogin.local/{profile_id}")
