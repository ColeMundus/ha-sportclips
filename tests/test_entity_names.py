"""Use recognizable defaults without replacing registry customizations."""

from homeassistant.helpers import entity_registry as er

from tests.test_ha import setup_entry


async def test_new_entities_have_service_prefix(hass, http):
    await setup_entry(hass, http)
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("sensor", "sportclips", "synthetic-store_wait")
        == "sensor.sports_clips_example_salon_estimated_wait"
    )
    assert (
        registry.async_get_entity_id(
            "binary_sensor", "sportclips", "synthetic-store_status"
        )
        == "binary_sensor.sports_clips_example_salon_store_status"
    )
    assert (
        hass.states.get("sensor.sports_clips_example_salon_estimated_wait").attributes[
            "friendly_name"
        ]
        == "Sport Clips Example Salon Estimated wait"
    )


async def test_custom_entity_identity_and_name_survive_reload(hass, http):
    entry = await setup_entry(hass, http)
    registry = er.async_get(hass)
    old_id = registry.async_get_entity_id(
        "sensor", "sportclips", "synthetic-store_wait"
    )
    registry.async_update_entity(
        old_id, new_entity_id="sensor.my_haircut_wait", name="My haircut wait"
    )
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    record = registry.async_get("sensor.my_haircut_wait")
    assert record.unique_id == "synthetic-store_wait"
    assert record.name == "My haircut wait"
    assert hass.states.get("sensor.my_haircut_wait").state == "0"
