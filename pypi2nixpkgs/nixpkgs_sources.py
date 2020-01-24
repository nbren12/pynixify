from typing import Sequence
from dataclasses import dataclass
from packaging.utils import canonicalize_name
from packaging.requirements import Requirement
from packaging.version import Version, parse
from pypi2nixpkgs.exceptions import PackageNotFound

@dataclass
class PyDerivation:
    attr: str
    version: Version


class NixpkgsData:
    def __init__(self, data):
        self.__data = {canonicalize_name(k): v for (k, v) in data.items()}

    def from_pypi_name(self, name: str) -> Sequence[PyDerivation]:
        try:
            data = self.__data[canonicalize_name(name)]
        except KeyError:
            raise PackageNotFound(f'{name} is not defined in nixpkgs')
        return [
            PyDerivation(attr=drv['attr'], version=parse(drv['version']))
            for drv in data
        ]

    def from_requirement(self, req: Requirement) -> Sequence[PyDerivation]:
        drvs = self.from_pypi_name(req.name)
        return [drv for drv in drvs if str(drv.version) in req.specifier]
