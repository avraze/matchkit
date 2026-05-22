import bpy
from . models import (
    check_dependencies,
    get_standard_model, get_hybrid_model,
    STANDARD_MODELS, HYBRID_MODELS
)


# ─────────────────────────────────────────────
#  3D VIEWPORT PANELS
# ─────────────────────────────────────────────

class MATCHKIT_PT_main_panel(bpy.types.Panel):
    bl_label       = "MatchKit"
    bl_idname      = "MATCHKIT_PT_main_panel"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "MatchKit"

    def draw_header(self, context):
        self.layout.label(text="", icon='CAMERA_DATA')

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text="v0.5.7", icon='INFO')
        row.operator("matchkit.reload", text="", icon='FILE_REFRESH')


class MATCHKIT_PT_proxy_geometry(bpy.types.Panel):
    bl_label       = "Proxy Geometry"
    bl_idname      = "MATCHKIT_PT_proxy_geometry"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "MatchKit"
    bl_parent_id   = "MATCHKIT_PT_main_panel"

    def draw(self, context):
        layout       = self.layout
        obj          = context.active_object
        is_edit_mesh = (obj is not None and obj.type == 'MESH' and context.mode == 'EDIT_MESH')
        has_camera   = context.scene.camera is not None

        col = layout.column(align=True)
        col.label(text="Triangulate:", icon='MOD_TRIANGULATE')
        row = col.row(align=True)
        row.enabled = is_edit_mesh and has_camera
        row.operator("matchkit.camera_triangulate", text="From Camera View", icon='CAMERA_DATA')

        if not has_camera:
            col.label(text="  No camera in scene", icon='ERROR')
        elif not is_edit_mesh:
            col.label(text="  Enter Edit Mode first", icon='INFO')


# ─────────────────────────────────────────────
#  MOVIE CLIP EDITOR PANELS
# ─────────────────────────────────────────────

class MATCHKIT_PT_clip_main(bpy.types.Panel):
    bl_label       = "MatchKit"
    bl_idname      = "MATCHKIT_PT_clip_main"
    bl_space_type  = 'CLIP_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "MatchKit"

    def draw_header(self, context):
        self.layout.label(text="", icon='CAMERA_DATA')

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text="v0.5.7", icon='INFO')
        row.operator("matchkit.reload", text="", icon='FILE_REFRESH')


class MATCHKIT_PT_clip_autotrack(bpy.types.Panel):
    bl_label       = "Auto Track"
    bl_idname      = "MATCHKIT_PT_clip_autotrack"
    bl_space_type  = 'CLIP_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "MatchKit"
    bl_parent_id   = "MATCHKIT_PT_clip_main"

    def draw(self, context):
        layout    = self.layout
        props     = context.scene.matchkit_props
        clip      = context.edit_movieclip
        is_hybrid = props.tracking_mode == 'HYBRID'

        # ── Mode selector ──
        col = layout.column(align=True)
        col.label(text="Mode:", icon='SHADERFX')
        row = col.row(align=True)
        row.prop_enum(props, "tracking_mode", 'STANDARD')
        row.prop_enum(props, "tracking_mode", 'HYBRID')

        layout.separator()

        # ── Tracker Engine (greyed out in Hybrid mode) ──
        col = layout.column(align=True)
        col.enabled = not is_hybrid
        col.label(text="Tracker Engine:", icon='FORCE_FORCE')
        col.prop(props, "standard_model", text="")

        # Show status for selected standard model
        if not is_hybrid:
            s_model  = get_standard_model(props.standard_model)
            all_ok, missing = check_dependencies(props.standard_model, is_hybrid=False)
            if all_ok:
                col.label(text="  Ready", icon='CHECKMARK')
            else:
                col.label(text=f"  Missing: {', '.join(missing)}", icon='ERROR')
                col.operator("matchkit.setup_dependencies",
                             text=f"Install {s_model['name']}", icon='IMPORT')

        layout.separator()

        # ── Hybrid Model (only visible in Hybrid mode) ──
        if is_hybrid:
            col = layout.column(align=True)
            col.label(text="Hybrid Model:", icon='LINKED')
            col.prop(props, "hybrid_model", text="")

            h_model  = get_hybrid_model(props.hybrid_model)
            all_ok, missing = check_dependencies(props.hybrid_model, is_hybrid=True)
            if all_ok:
                col.label(text="  Ready", icon='CHECKMARK')
            else:
                col.label(text=f"  Missing: {', '.join(missing)}", icon='ERROR')
                col.operator("matchkit.setup_dependencies",
                             text=f"Install dependencies", icon='IMPORT')

            layout.separator()

        # ── Quality ──
        col = layout.column(align=True)
        col.label(text="Quality:", icon='SETTINGS')

        if is_hybrid:
            # Quality mode toggle — Linked or Split
            row = col.row(align=True)
            row.prop_enum(props, "hybrid_quality_mode", 'LINKED')
            row.prop_enum(props, "hybrid_quality_mode", 'SPLIT')
            col.separator()

            if props.hybrid_quality_mode == 'LINKED':
                # One quality controls both
                col.label(text="Detection + Tracking:")
                row = col.row(align=True)
                row.prop_enum(props, "tracker_quality", 'FAST')
                row.prop_enum(props, "tracker_quality", 'BALANCED')
                row.prop_enum(props, "tracker_quality", 'BEST')
            else:
                # Split — two separate quality controls
                col.label(text="Detection (OpenCV):")
                row = col.row(align=True)
                row.prop_enum(props, "hybrid_detection_quality", 'FAST')
                row.prop_enum(props, "hybrid_detection_quality", 'BALANCED')
                row.prop_enum(props, "hybrid_detection_quality", 'BEST')
                col.separator()
                col.label(text="Tracking (CoTracker3):")
                row = col.row(align=True)
                row.prop_enum(props, "hybrid_tracking_quality", 'FAST')
                row.prop_enum(props, "hybrid_tracking_quality", 'BALANCED')
                row.prop_enum(props, "hybrid_tracking_quality", 'BEST')
        else:
            # Standard mode — single quality
            row = col.row(align=True)
            row.prop_enum(props, "tracker_quality", 'FAST')
            row.prop_enum(props, "tracker_quality", 'BALANCED')
            row.prop_enum(props, "tracker_quality", 'BEST')

        layout.separator()

        # ── Settings ──
        col = layout.column(align=True)
        col.label(text="Settings:", icon='PREFERENCES')
        col.prop(props, "auto_track_max_points")
        col.prop(props, "auto_track_margin")
        col.separator()
        col.label(text="Grid (foreground/bg balance):")
        row = col.row(align=True)
        row.prop(props, "auto_track_grid_cols", text="Cols")
        row.prop(props, "auto_track_grid_rows", text="Rows")
        zones = props.auto_track_grid_cols * props.auto_track_grid_rows
        pts   = max(1, props.auto_track_max_points // zones)
        col.label(text=f"  {zones} zones  →  ~{pts} pts each", icon='INFO')

        layout.separator()

        # ── Auto Track button ──
        # Determine if ready to track
        if is_hybrid:
            all_ok, _ = check_dependencies(props.hybrid_model, is_hybrid=True)
        else:
            all_ok, _ = check_dependencies(props.standard_model, is_hybrid=False)

        col = layout.column(align=True)
        col.enabled = all_ok and clip is not None
        col.operator("matchkit.auto_track", text="Auto Track", icon='TRACKING_FORWARDS')

        if not clip:
            layout.label(text="  Load footage first", icon='ERROR')
        elif not all_ok:
            layout.label(text="  Install model above first", icon='ERROR')



class MATCHKIT_PT_clip_selection(bpy.types.Panel):
    bl_label       = "Selection Tools"
    bl_idname      = "MATCHKIT_PT_clip_selection"
    bl_space_type  = 'CLIP_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "MatchKit"
    bl_parent_id   = "MATCHKIT_PT_clip_main"

    def draw(self, context):
        layout = self.layout
        clip   = context.edit_movieclip

        # ── View switcher ──
        col = layout.column(align=True)
        col.label(text="View:", icon='RESTRICT_VIEW_OFF')
        row = col.row(align=True)
        row.operator("matchkit.switch_to_clip",  text="Clip",  icon='SEQUENCE')
        row.operator("matchkit.switch_to_graph", text="Graph", icon='GRAPH')

        layout.separator()

        # ── Sync ──
        col = layout.column(align=True)
        col.label(text="Sync:", icon='UV_SYNC_SELECT')
        col.enabled = clip is not None
        col.operator("matchkit.sync_selection",
                     text="Sync Graph → Viewer",
                     icon='TRACKING')
        col.label(text="  Selects in viewer + activates", icon='INFO')

        layout.separator()

        # ── Select helpers ──
        col = layout.column(align=True)
        col.label(text="Select:", icon='RESTRICT_SELECT_OFF')
        col.enabled = clip is not None
        col.operator("matchkit.select_bad_tracks",
                     text="Select Bad Tracks",
                     icon='ERROR')
        col.label(text="  Tracks with few markers", icon='INFO')

# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = [
    MATCHKIT_PT_main_panel,
    MATCHKIT_PT_proxy_geometry,
    MATCHKIT_PT_clip_main,
    MATCHKIT_PT_clip_autotrack,
    MATCHKIT_PT_clip_selection,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
