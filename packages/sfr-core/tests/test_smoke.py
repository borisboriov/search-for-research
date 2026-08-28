import sfr_core
import sfr_etl


def test_packages_importable() -> None:
    assert sfr_core.__version__
    assert sfr_etl.__version__
