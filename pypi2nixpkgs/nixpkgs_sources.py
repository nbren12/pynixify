import json
import asyncio
from pathlib import Path
from typing import Sequence
from dataclasses import dataclass
from packaging.utils import canonicalize_name
from packaging.requirements import Requirement
from packaging.version import Version, parse
from pypi2nixpkgs.base import Package
from pypi2nixpkgs.exceptions import PackageNotFound

@dataclass
class NixPackage(Package):
    attr: str

    async def source(self, extra_args=[]):
        args = [
            '--no-out-link',
            '<nixpkgs>',
            '-A',
            f'python37Packages."{self.attr}".src',
        ]
        args += extra_args
        return await run_nix_build(*args)


class NixpkgsData:
    def __init__(self, data):
        self.__data = {canonicalize_name(k): v for (k, v) in data.items()}

    def from_pypi_name(self, name: str) -> Sequence[NixPackage]:
        try:
            data = self.__data[canonicalize_name(name)]
        except KeyError:
            raise PackageNotFound(f'{name} is not defined in nixpkgs')
        return [
            NixPackage(attr=drv['attr'], version=parse(drv['version']))
            for drv in data
        ]

    def from_requirement(self, req: Requirement) -> Sequence[NixPackage]:
        drvs = self.from_pypi_name(req.name)
        return [drv for drv in drvs if str(drv.version) in req.specifier]


async def load_nixpkgs_data(extra_args):
    nix_expression_path = Path(__file__).parent.parent / "pythonPackages.nix"
    args = [
        '--eval',
        '--strict',
        '--json',
        str(nix_expression_path),
    ]
    args += extra_args
    proc = await asyncio.create_subprocess_exec(
        'nix-instantiate', *args, stdout=asyncio.subprocess.PIPE)
    (stdout, _) = await proc.communicate()
    status = await proc.wait()
    assert status == 0
    ret = json.loads(stdout)
    return ret


async def run_nix_build(*args: Sequence[str]) -> Path:
    proc = await asyncio.create_subprocess_exec(
        'nix-build', *args, stdout=asyncio.subprocess.PIPE)
    (stdout, _) = await proc.communicate()
    status = await proc.wait()
    assert status == 0
    return Path(stdout.strip().decode())