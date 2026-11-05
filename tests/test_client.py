import aiohttp

from custom_components.sportclips.client import SportClipsClient

BASE = "https://api.sportclipsinc.com/api/v1/store"


async def test_search_geographic_suggestions(http):
    http.get(
        BASE + "/search?searchText=Example",
        payload={
            "response": {
                "searchedLocations": [
                    {
                        "placeName": "Example, State",
                        "latitude": 35.0,
                        "longitude": -90.0,
                    }
                ]
            }
        },
    )
    async with aiohttp.ClientSession() as session:
        locations = await SportClipsClient(session).search("Example")
    assert [(item.name, item.latitude, item.longitude) for item in locations] == [
        ("Example, State", 35.0, -90.0)
    ]
