from __future__ import annotations

import pytest

from isaac.mobile_manipulator import (
    IWHUB_USD_PATH,
    ROBOTIQ_BASE_MOUNT_CANDIDATES,
    ROBOTIQ_2F140_USD_PATH,
    UR10E_USD_PATH,
    MobileManipulatorConfig,
    parse_numeric_tuple,
    resolve_asset_path,
)


def test_catalog_asset_paths_match_selected_robot() -> None:
    assert IWHUB_USD_PATH == "/Isaac/Robots/Idealworks/iwhub/iw_hub.usd"
    assert UR10E_USD_PATH == "/Isaac/Robots/UniversalRobots/ur10e/ur10e.usd"
    assert ROBOTIQ_2F140_USD_PATH.endswith("/Robotiq_2F_140_config.usd")
    assert ROBOTIQ_BASE_MOUNT_CANDIDATES[0] == "robotiq_base_link"


def test_resolve_asset_path_joins_catalog_path_to_assets_root() -> None:
    assert resolve_asset_path("omniverse://server/NVIDIA/Assets", IWHUB_USD_PATH) == (
        "omniverse://server/NVIDIA/Assets/Isaac/Robots/Idealworks/iwhub/iw_hub.usd"
    )


@pytest.mark.parametrize(
    "configured",
    ["omniverse://custom/robot.usd", "https://example.test/robot.usd"],
)
def test_resolve_asset_path_preserves_uri_override(configured: str) -> None:
    assert resolve_asset_path("omniverse://ignored", configured) == configured


def test_parse_numeric_tuple_rejects_wrong_length_and_non_finite_values() -> None:
    with pytest.raises(ValueError, match="3 comma-separated"):
        parse_numeric_tuple("1,2", length=3, setting_name="OFFSET")
    with pytest.raises(ValueError, match="finite"):
        parse_numeric_tuple("1,nan,3", length=3, setting_name="OFFSET")


def test_config_from_env_exposes_mount_and_pose_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OMNIGUARD_IWHUB_ARM_MOUNT", "custom_payload_mount")
    monkeypatch.setenv("OMNIGUARD_ARM_MOUNT_TRANSLATION", "0.1,0.2,0.7")
    monkeypatch.setenv("OMNIGUARD_UR10E_STOW_DEGREES", "1,2,3,4,5,6")

    config = MobileManipulatorConfig.from_env()

    assert config.iwhub_arm_mount == "custom_payload_mount"
    assert config.arm_offset.translation == (0.1, 0.2, 0.7)
    assert config.ur10e_stow_degrees == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)