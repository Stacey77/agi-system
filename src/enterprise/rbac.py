"""Role-based access control for enterprise governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Permission:
    name: str
    description: str = ""


@dataclass
class Role:
    name: str
    permissions: Set[str] = field(default_factory=set)
    description: str = ""

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions or "*" in self.permissions


_DEFAULT_PERMISSIONS: List[Permission] = [
    Permission("agents:read", "List and inspect agents"),
    Permission("agents:write", "Create and update agents"),
    Permission("agents:delete", "Remove agents"),
    Permission("tasks:read", "View tasks"),
    Permission("tasks:write", "Submit tasks"),
    Permission("tasks:delete", "Cancel or delete tasks"),
    Permission("memory:read", "Read memory entries"),
    Permission("memory:write", "Write memory entries"),
    Permission("sessions:read", "View sessions"),
    Permission("sessions:write", "Manage sessions"),
    Permission("workforce:read", "View workforce status"),
    Permission("workforce:write", "Hire/fire workers, assign tasks"),
    Permission("audit:read", "Read audit logs"),
    Permission("audit:purge", "Purge audit log entries"),
    Permission("tenants:read", "View tenants"),
    Permission("tenants:write", "Create/update tenants"),
    Permission("rbac:read", "View roles and permissions"),
    Permission("rbac:write", "Manage roles and assignments"),
    Permission("integrations:read", "View integration status"),
    Permission("integrations:write", "Configure integrations"),
]

_DEFAULT_ROLES: List[Dict] = [
    {
        "name": "super_admin",
        "description": "Full platform access",
        "permissions": {"*"},
    },
    {
        "name": "admin",
        "description": "Administrative access excluding super-admin ops",
        "permissions": {
            "agents:read", "agents:write", "agents:delete",
            "tasks:read", "tasks:write", "tasks:delete",
            "memory:read", "memory:write",
            "sessions:read", "sessions:write",
            "workforce:read", "workforce:write",
            "audit:read",
            "tenants:read",
            "rbac:read",
            "integrations:read", "integrations:write",
        },
    },
    {
        "name": "operator",
        "description": "Day-to-day operational access",
        "permissions": {
            "agents:read", "agents:write",
            "tasks:read", "tasks:write",
            "memory:read", "memory:write",
            "sessions:read", "sessions:write",
            "workforce:read", "workforce:write",
            "audit:read",
            "integrations:read",
        },
    },
    {
        "name": "viewer",
        "description": "Read-only access",
        "permissions": {
            "agents:read",
            "tasks:read",
            "memory:read",
            "sessions:read",
            "workforce:read",
            "audit:read",
            "integrations:read",
        },
    },
]


class RBACManager:
    """In-memory RBAC manager seeded with default roles and permissions."""

    def __init__(self) -> None:
        self._permissions: Dict[str, Permission] = {}
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, Set[str]] = {}
        self._seed()

    def _seed(self) -> None:
        for p in _DEFAULT_PERMISSIONS:
            self._permissions[p.name] = p
        for rd in _DEFAULT_ROLES:
            role = Role(
                name=rd["name"],
                description=rd.get("description", ""),
                permissions=set(rd["permissions"]),
            )
            self._roles[role.name] = role

    # --- Permissions ---

    def list_permissions(self) -> List[Permission]:
        return list(self._permissions.values())

    def add_permission(self, name: str, description: str = "") -> Permission:
        p = Permission(name=name, description=description)
        self._permissions[name] = p
        return p

    def remove_permission(self, name: str) -> bool:
        if name not in self._permissions:
            return False
        del self._permissions[name]
        for role in self._roles.values():
            role.permissions.discard(name)
        return True

    # --- Roles ---

    def list_roles(self) -> List[Role]:
        return list(self._roles.values())

    def get_role(self, name: str) -> Optional[Role]:
        return self._roles.get(name)

    def create_role(
        self, name: str, permissions: Optional[List[str]] = None, description: str = ""
    ) -> Role:
        role = Role(name=name, description=description, permissions=set(permissions or []))
        self._roles[name] = role
        return role

    def delete_role(self, name: str) -> bool:
        if name not in self._roles:
            return False
        del self._roles[name]
        for user_roles in self._user_roles.values():
            user_roles.discard(name)
        return True

    def add_permission_to_role(self, role_name: str, permission: str) -> bool:
        role = self._roles.get(role_name)
        if role is None:
            return False
        role.permissions.add(permission)
        return True

    def remove_permission_from_role(self, role_name: str, permission: str) -> bool:
        role = self._roles.get(role_name)
        if role is None:
            return False
        role.permissions.discard(permission)
        return True

    # --- User assignments ---

    def assign_role(self, user_id: str, role_name: str) -> bool:
        if role_name not in self._roles:
            return False
        self._user_roles.setdefault(user_id, set()).add(role_name)
        return True

    def revoke_role(self, user_id: str, role_name: str) -> bool:
        if user_id not in self._user_roles:
            return False
        self._user_roles[user_id].discard(role_name)
        return True

    def get_user_roles(self, user_id: str) -> List[str]:
        return list(self._user_roles.get(user_id, set()))

    def check_permission(self, user_id: str, permission: str) -> bool:
        for role_name in self._user_roles.get(user_id, set()):
            role = self._roles.get(role_name)
            if role and role.has_permission(permission):
                return True
        return False

    def get_user_permissions(self, user_id: str) -> Set[str]:
        perms: Set[str] = set()
        for role_name in self._user_roles.get(user_id, set()):
            role = self._roles.get(role_name)
            if role:
                if "*" in role.permissions:
                    return {"*"}
                perms |= role.permissions
        return perms

    def __repr__(self) -> str:
        return f"RBACManager(roles={len(self._roles)}, permissions={len(self._permissions)})"
