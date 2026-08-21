from __future__ import annotations

import pytest

from isaac.mobile_manipulator import (
    IWHUB_USD_PATH,
    MOBILE_MANIPULATOR_USD_PATH,
    ROBOTIQ_BASE_MOUNT_CANDIDATES,
    ROBOTIQ_2F140_USD_PATH,
    RIDGEBACK_FRANKA_USD_PATH,
    RIDGEBACK_UR5_USD_PATH,
    UR10E_USD_PATH,
    MobileManipulatorConfig,
    parse_bool_setting,
    parse_numeric_tuple,
    resolve_asset_path,
)


def test_catalog_asset_paths_match_selected_robot() -> None:
    assert MOBILE_MANIPULATOR_USD_PATH == RIDGEBACK_FRANKA_USD_PATH
    assert MOBILE_MANIPULATOR_USD_PATH == (
        "/Isaac/Robots/Clearpath/RidgebackFranka/ridgeback_franka.usd"
    )
    assert RIDGEBACK_UR5_USD_PATH == "/Isaac/Robots/Clearpath/RidgebackUr/ridgeback_ur5.usd"


def test_composite_fallback_asset_paths_remain_available() -> None:
    assert IWHUB_USD_PATH == "/Isaac/Robots/Idealworks/iwhub/iw_hub.usd"
    assert UR10E_USD_PATH == "/Isaac/Robots/UniversalRobots/ur10e/ur10e.usd"
    assert ROBOTIQ_2F140_USD_PATH.endswith("/Robotiq_2F_140_config.usd")
    assert ROBOTIQ_BASE_MOUNT_CANDIDATES[0] == "robotiq_base_link"


def test_resolve_asset_path_joins_catalog_path_to_assets_root() -> None:
    assert resolve_asset_path("omniverse://server/NVIDIA/Assets", MOBILE_MANIPULATOR_USD_PATH) == (
        "omniverse://server/NVIDIA/Assets/Isaac/Robots/Clearpath/RidgebackFranka/ridgeback_franka.usd"
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


def test_parse_bool_setting_accepts_common_values_and_rejects_unknown() -> None:
    assert parse_bool_setting("true", setting_name="FLAG") is True
    assert parse_bool_setting("0", setting_name="FLAG") is False
    with pytest.raises(ValueError, match="FLAG must be boolean"):
        parse_bool_setting("sometimes", setting_name="FLAG")


def test_config_from_env_exposes_mount_and_pose_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OMNIGUARD_MOBILE_MANIPULATOR_USD", RIDGEBACK_UR5_USD_PATH)
    monkeypatch.setenv("OMNIGUARD_USE_COMPOSITE_MOBILE_MANIPULATOR", "true")
    monkeypatch.setenv("OMNIGUARD_IWHUB_ARM_MOUNT", "custom_payload_mount")
    monkeypatch.setenv("OMNIGUARD_ARM_MOUNT_TRANSLATION", "0.1,0.2,0.7")
    monkeypatch.setenv("OMNIGUARD_UR10E_STOW_DEGREES", "1,2,3,4,5,6")

    config = MobileManipulatorConfig.from_env()

    assert config.mobile_manipulator_usd == RIDGEBACK_UR5_USD_PATH
    assert config.use_composite_assets is True
    assert config.iwhub_arm_mount == "custom_payload_mount"
    assert config.arm_offset.translation == (0.1, 0.2, 0.7)
    assert config.ur10e_stow_degrees == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)