"""Supported registry migration keeps user settings without obsolete entities."""

from dataclasses import asdict

import pytest
from homeassistant.components.homeassistant.exposed_entities import (
    KNOWN_ASSISTANTS,
    async_should_expose,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sportclips import _migrate_status_registry
from tests.test_ha import setup_entry
from tests.test_metadata import STORE, envelope
from tests.test_validation import SALON


@pytest.mark.parametrize("disabled", [None, er.RegistryEntryDisabler.USER])
@pytest.mark.parametrize("disable_new", [False, True])
async def test_legacy_status_migration(hass, http, disabled, disable_new):
    entry = MockConfigEntry(
        domain="sportclips",
        unique_id=SALON.id,
        data=asdict(SALON),
        options={"polling_interval": 7},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        "sportclips",
        f"{SALON.id}_status",
        config_entry=entry,
        suggested_object_id="my_store",
        disabled_by=disabled,
        hidden_by=er.RegistryEntryHider.USER,
    )
    old = registry.async_update_entity(
        old.entity_id, name="My store", icon="mdi:store", aliases=["Haircut shop"]
    )
    wait = registry.async_get_or_create(
        "sensor",
        "sportclips",
        f"{SALON.id}_wait",
        config_entry=entry,
        suggested_object_id="my_wait",
    )
    wait = registry.async_update_entity(wait.entity_id, name="My wait")
    data, options = dict(entry.data), dict(entry.options)
    hass.config_entries.async_update_entry(entry, pref_disable_new_entities=disable_new)
    http.post(payload=envelope(STORE))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(old.entity_id) is None
    migrated = registry.async_get("binary_sensor.my_store")
    assert migrated.unique_id == old.unique_id
    for key in (
        "name",
        "icon",
        "aliases",
        "disabled_by",
        "hidden_by",
        "area_id",
        "labels",
        "categories",
    ):
        assert getattr(migrated, key) == getattr(old, key)
    assert migrated.original_device_class == "opening"
    assert registry.async_get(wait.entity_id).id == wait.id
    assert registry.async_get(wait.entity_id).name == "My wait"
    assert dict(entry.data) == data and dict(entry.options) == options
    assert len(http.requests) == 1
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get("binary_sensor.my_store").id == migrated.id
    assert registry.async_get_entity_id("sensor", "sportclips", old.unique_id) is None
    assert len(http.requests) == 1


@pytest.mark.parametrize("expose", [None, False, True])
@pytest.mark.parametrize("seed_options", [False, True])
async def test_migration_preserves_generic_options_and_exposure(
    hass, http, expose, seed_options
):
    """An enum's default non-exposure must not become Opening's opt-out default."""
    assert await async_setup_component(hass, "homeassistant", {})
    entry = MockConfigEntry(domain="sportclips", data=asdict(SALON))
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", "sportclips", f"{SALON.id}_status", config_entry=entry
    )
    generic = {"nested": {"custom": ["kept"]}}
    registry.async_update_entity_options(old.entity_id, "custom_namespace", generic)
    registry.async_update_entity_options(
        old.entity_id, "sensor", {"display_precision": 3}
    )
    for assistant in KNOWN_ASSISTANTS:
        options = {"custom_option": "kept"} if seed_options else {}
        if expose is not None:
            options["should_expose"] = expose
        registry.async_update_entity_options(old.entity_id, assistant, options)
    # Do not query exposure before migration: that would persist a default and
    # hide the missing-options case that can otherwise widen Assist exposure.
    http.post(payload=envelope(STORE))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    new_id = registry.async_get_entity_id("binary_sensor", "sportclips", old.unique_id)
    new = registry.async_get(new_id)
    assert new.options["custom_namespace"] == generic
    assert "sensor" not in new.options
    for assistant in KNOWN_ASSISTANTS:
        expected = {"custom_option": "kept"} if seed_options else {}
        expected["should_expose"] = expose is True
        assert new.options[assistant] == expected
        assert async_should_expose(hass, assistant, new_id) is (expose is True)
    before_reload = new.options
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(new_id).options == before_reload


async def test_migration_does_not_steal_colliding_entity_id(hass, http):
    entry = MockConfigEntry(domain="sportclips", unique_id=SALON.id, data=asdict(SALON))
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        "sportclips",
        f"{SALON.id}_status",
        config_entry=entry,
        suggested_object_id="my_store",
    )
    collision = registry.async_get_or_create(
        "binary_sensor",
        "sportclips",
        "other_status",
        config_entry=entry,
        suggested_object_id="my_store",
    )
    http.post(payload=envelope(STORE))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(collision.entity_id) == collision
    assert registry.async_get(old.entity_id) is None
    assert (
        registry.async_get_entity_id("binary_sensor", "sportclips", old.unique_id)
        == "binary_sensor.my_store_2"
    )


async def test_existing_replacement_keeps_its_customizations(hass, http):
    entry = await setup_entry(hass, http)
    registry = er.async_get(hass)
    new_id = registry.async_get_entity_id(
        "binary_sensor", "sportclips", f"{SALON.id}_status"
    )
    new = registry.async_update_entity(new_id, name="New custom name")
    old = registry.async_get_or_create(
        "sensor", "sportclips", new.unique_id, config_entry=entry
    )
    registry.async_update_entity(old.entity_id, name="Obsolete name")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(old.entity_id) is None
    assert registry.async_get(new_id).name == "New custom name"
    assert registry.async_get(new_id).id == new.id


@pytest.mark.parametrize("foreign_domain", ["sensor", "binary_sensor"])
async def test_migration_never_touches_foreign_entry(hass, foreign_domain):
    entry = MockConfigEntry(domain="sportclips", data=asdict(SALON))
    other = MockConfigEntry(domain="sportclips", data=asdict(SALON))
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        "sportclips",
        f"{SALON.id}_status",
        config_entry=other if foreign_domain == "sensor" else entry,
    )
    if foreign_domain == "binary_sensor":
        new = registry.async_get_or_create(
            "binary_sensor", "sportclips", old.unique_id, config_entry=other
        )
    _migrate_status_registry(hass, entry)
    assert registry.async_get(old.entity_id) == old
    if foreign_domain == "binary_sensor":
        assert registry.async_get(new.entity_id) == new


async def test_migration_preserves_device_after_full_setup(hass, http):
    entry = MockConfigEntry(domain="sportclips", data=asdict(SALON))
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("sportclips", SALON.id)},
        name="My salon",
    )
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        "sportclips",
        f"{SALON.id}_status",
        config_entry=entry,
        device_id=device.id,
    )
    http.post(payload=envelope(STORE))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    new_id = registry.async_get_entity_id("binary_sensor", "sportclips", old.unique_id)
    assert registry.async_get(new_id).device_id == device.id
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(new_id).device_id == device.id


async def test_setup_does_not_claim_foreign_replacement(hass, http):
    entry = MockConfigEntry(domain="sportclips", data=asdict(SALON))
    other = MockConfigEntry(domain="other", data=asdict(SALON))
    entry.add_to_hass(hass)
    other.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", "sportclips", f"{SALON.id}_status", config_entry=entry
    )
    foreign = registry.async_get_or_create(
        "binary_sensor", "sportclips", old.unique_id, config_entry=other
    )
    http.post(payload=envelope(STORE))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(foreign.entity_id) == foreign
    assert registry.async_get(old.entity_id) == old
    assert hass.states.get(foreign.entity_id) is None


async def test_failed_initial_refresh_does_not_migrate_registry(hass, http):
    entry = MockConfigEntry(domain="sportclips", data=asdict(SALON))
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", "sportclips", f"{SALON.id}_status", config_entry=entry
    )
    http.post(status=503)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert registry.async_get(old.entity_id) == old
    assert (
        registry.async_get_entity_id("binary_sensor", "sportclips", old.unique_id)
        is None
    )
