import json
import pytest
from pathlib import Path
from pypi2nixpkgs.base import Package
from packaging.requirements import Requirement
from pypi2nixpkgs.package_requirements import PackageRequirements
from pypi2nixpkgs.nixpkgs_sources import (
    NixpkgsData,
)
from pypi2nixpkgs.version_chooser import (
    VersionChooser,
)
from pypi2nixpkgs.exceptions import (
    NoMatchingVersionFound,
    PackageNotFound,
)


ZSTD_DATA = {
    'zstd': [{
        'attr': 'zstd',
        'pypiName': 'zstd',
        'src': "mirror://pypi/z/zstd/zstd-1.4.4.0.tar.gz",
        'version': "1.4.4.0",
    }]
}


MULTIVERSION_DATA = {
    "a": [
        {"attr": "a1", "pypiName": "a", "version": "1.0.1"},
        {"attr": "a24", "pypiName": "a", "version": "2.4"},
        {"attr": "a3", "pypiName": "a", "version": "3.0.0"},
        {"attr": "a2", "pypiName": "a", "version": "2.3"},
    ]
}


with (Path(__file__).parent / "nixpkgs_packages.json").open() as fp:
    NIXPKGS_JSON = json.load(fp)


def dummy_package_requirements(hardcoded_reqs={}):
    async def f(package: Package) -> PackageRequirements:
        nonlocal hardcoded_reqs
        # Don't use the data inside the result file, just use it to prevent
        # PackageRequirements.__init__ from failing
        (b, t, r) = hardcoded_reqs.get(package.attr, ([], [], []))
        reqs = PackageRequirements(
            Path(__file__).parent / "parse_setuppy_data_result")
        reqs.build_requirements = b
        reqs.test_requirements = t
        reqs.runtime_requirements = r
        return reqs
    return f


@pytest.mark.asyncio
async def test_nixpkgs_package():
    nixpkgs = NixpkgsData(ZSTD_DATA)
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    await c.require(Requirement('zstd==1.4.4.0'))


@pytest.mark.asyncio
async def test_package_for_canonicalizes():
    nixpkgs = NixpkgsData(ZSTD_DATA)
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    await c.require(Requirement('ZSTD==1.4.4.0'))
    assert c.package_for('zstd') is c.package_for('ZSTD')


@pytest.mark.asyncio
async def test_invalid_package():
    nixpkgs = NixpkgsData({})
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    with pytest.raises(PackageNotFound):
        await c.require(Requirement('zstd==1.4.4.0'))


@pytest.mark.asyncio
async def test_no_matching_version():
    nixpkgs = NixpkgsData(ZSTD_DATA)
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    with pytest.raises(NoMatchingVersionFound):
        await c.require(Requirement('zstd>1.4.4.0'))


@pytest.mark.asyncio
async def test_no_matching_version_on_second_require():
    nixpkgs = NixpkgsData(ZSTD_DATA)
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    await c.require(Requirement('zstd==1.4.4.0'))
    with pytest.raises(NoMatchingVersionFound):
        await c.require(Requirement('zstd<1.4.4.0'))

@pytest.mark.asyncio
async def test_no_matching_version_with_previous_requirements():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    await c.require(Requirement('django==2.1.14'))
    with pytest.raises(NoMatchingVersionFound):
        await c.require(Requirement('django>=2.2'))


@pytest.mark.asyncio
async def test_multi_nixpkgs_versions():
    nixpkgs = NixpkgsData(MULTIVERSION_DATA)
    c = VersionChooser(nixpkgs, dummy_package_requirements())
    await c.require(Requirement('a>=2.0.0'))
    assert str(c.package_for('a').version) == '3.0.0'


@pytest.mark.asyncio
async def test_uses_runtime_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_package_requirements({
        "django_2_2": ([], [], [Requirement('pytz')]),
    }))
    await c.require(Requirement('django>=2.2'))
    assert c.package_for('django')
    assert c.package_for('pytz')
    assert str(c.package_for('pytz').version) == '2019.3'


@pytest.mark.asyncio
async def test_uses_test_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_package_requirements({
        "django_2_2": ([], [Requirement('pytest')], []),
    }))
    await c.require(Requirement('django>=2.2'))
    assert c.package_for('django')
    assert c.package_for('pytest')


@pytest.mark.asyncio
async def test_does_not_user_build_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_package_requirements({
        "pytz": ([Requirement('setuptools_scm')], [], []),
    }))
    await c.require(Requirement('pytz'))
    assert c.package_for('pytz')
    assert c.package_for('setuptools_scm') is None

@pytest.mark.asyncio
async def test_nixpkgs_transitive():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_package_requirements({
        'flask': ([], [], [Requirement("itsdangerous")]),
        'itsdangerous': ([], [Requirement('pytest')], []),
    }))
    await c.require(Requirement('flask'))
    assert c.package_for('flask')
    assert c.package_for('itsdangerous')
    assert c.package_for('pytest')


@pytest.mark.asyncio
async def test_circular_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_package_requirements({
        'flask': ([], [], [Requirement("itsdangerous")]),
        'itsdangerous': ([], [Requirement('flask')], []),
    }))
    await c.require(Requirement('flask'))
    assert c.package_for('flask')
    assert c.package_for('itsdangerous')