bl_info = {
    "name": "MatchKit",
    "author": "MatchKit",
    "version": (0, 5, 7),
    "blender": (3, 0, 0),
    "location": "View3D > N-Panel > MatchKit | Clip Editor > N-Panel > MatchKit",
    "description": "Matchmoving and VFX utility tools for Blender",
    "category": "3D View",
}

import bpy
from . import operators
from . import panels


def register():
    operators.register()
    panels.register()


def unregister():
    operators.unregister()
    panels.unregister()
