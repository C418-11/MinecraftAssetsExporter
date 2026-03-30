from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict


class FileInfo(TypedDict):
    hash: str
    size: int


class NodeStatus(StrEnum):
    VALID = "valid"
    PARTIAL = "partial"
    INVALID = "invalid"


@dataclass(kw_only=True)
class TreeNode:
    parent_path: str
    name: str
    path: str
    status: NodeStatus

    def __iter__(self):
        yield self.parent_path
        yield self.name
        yield self.path
        yield self.status


class NodeInfo(TypedDict):
    children: set[str]
    status: None | NodeStatus
