import bpy
import bmesh
import os
from . models import get_standard_model, get_hybrid_model, check_dependencies, STANDARD_MODELS, HYBRID_MODELS


# ─────────────────────────────────────────────
#  FEATURE 01 — Camera Projection Triangulate
# ─────────────────────────────────────────────

class MATCHKIT_OT_camera_triangulate(bpy.types.Operator):
    """Triangulate selected vertices based on current camera projection (like SynthEyes)"""
    bl_idname = "matchkit.camera_triangulate"
    bl_label  = "Camera Triangulate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.type == 'MESH'
            and context.mode == 'EDIT_MESH'
            and context.scene.camera is not None
        )

    def execute(self, context):
        try:
            from scipy.spatial import Delaunay
            import numpy as np
        except ImportError:
            self.report({'ERROR'}, "scipy not found. Use Setup Dependencies.")
            return {'CANCELLED'}

        obj        = context.active_object
        scene      = context.scene
        camera     = scene.camera
        cam_matrix = camera.matrix_world.inverted()
        render     = scene.render
        aspect     = render.resolution_x / render.resolution_y

        bpy.ops.object.mode_set(mode='OBJECT')
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()

        selected_verts = [v for v in bm.verts if v.select]
        if len(selected_verts) < 3:
            bm.free()
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'WARNING'}, "Select at least 3 vertices")
            return {'CANCELLED'}

        def project_to_camera(v_world):
            v_cam = cam_matrix @ v_world
            x = -v_cam.x / v_cam.z
            y = -v_cam.y / v_cam.z / aspect
            return (x, y)

        world_positions = [obj.matrix_world @ v.co for v in selected_verts]
        projected_2d    = np.array([project_to_camera(p) for p in world_positions])
        tri             = Delaunay(projected_2d)

        faces_created = 0
        for simplex in tri.simplices:
            v0, v1, v2 = [selected_verts[s] for s in simplex]
            try:
                bm.faces.new([v0, v1, v2])
                faces_created += 1
            except Exception:
                pass

        bm.to_mesh(me)
        bm.free()
        bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, f"MatchKit: Created {faces_created} triangles from camera projection")
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  FEATURE 02 — Setup Dependencies
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  FEATURE 04 — Selection Tools
# ─────────────────────────────────────────────

class MATCHKIT_OT_sync_selection(bpy.types.Operator):
    """Sync graph selection to viewer and activate track panel"""
    bl_idname  = "matchkit.sync_selection"
    bl_label   = "Sync Selection to Viewer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.edit_movieclip is not None

    def execute(self, context):
        clip   = context.edit_movieclip
        tracks = clip.tracking.tracks
        selected = [t for t in tracks if t.select]
        if not selected:
            self.report({'WARNING'}, "No tracks selected.")
            return {'CANCELLED'}
        tracks.active = selected[0]
        for area in context.screen.areas:
            if area.type == 'CLIP_EDITOR':
                area.spaces.active.view = 'CLIP'
                break
        self.report({'INFO'}, f"MatchKit: Synced {len(selected)} track(s) to viewer.")
        return {'FINISHED'}


class MATCHKIT_OT_select_bad_tracks(bpy.types.Operator):
    """Select tracks with few markers — likely drifted or lost"""
    bl_idname  = "matchkit.select_bad_tracks"
    bl_label   = "Select Bad Tracks"
    bl_options = {'REGISTER', 'UNDO'}
    threshold: bpy.props.IntProperty(name="Min Markers", default=10, min=1, max=500)

    @classmethod
    def poll(cls, context):
        return context.edit_movieclip is not None

    def execute(self, context):
        clip = context.edit_movieclip
        tracks = clip.tracking.tracks
        for t in tracks:
            t.select = False
        bad = [t for t in tracks if len(t.markers) < self.threshold]
        for t in bad:
            t.select = True
        if bad:
            tracks.active = bad[0]
        self.report({'INFO'}, f"MatchKit: Selected {len(bad)} bad tracks.")
        return {'FINISHED'}



class MATCHKIT_OT_switch_to_graph(bpy.types.Operator):
    """Switch clip editor to Graph view"""
    bl_idname  = "matchkit.switch_to_graph"
    bl_label   = "Graph View"
    bl_options = {'REGISTER'}

    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'CLIP_EDITOR':
                area.spaces.active.view = 'GRAPH'
                break
        return {'FINISHED'}


class MATCHKIT_OT_switch_to_clip(bpy.types.Operator):
    """Switch clip editor to Clip viewer"""
    bl_idname  = "matchkit.switch_to_clip"
    bl_label   = "Clip View"
    bl_options = {'REGISTER'}

    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'CLIP_EDITOR':
                area.spaces.active.view = 'CLIP'
                break
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  FEATURE 05 — Reload MatchKit
#  Clears cache and reloads addon cleanly
# ─────────────────────────────────────────────

class MATCHKIT_OT_reload(bpy.types.Operator):
    """Reload MatchKit cleanly — clears cache and reloads all modules"""
    bl_idname  = "matchkit.reload"
    bl_label   = "Reload MatchKit"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import sys
        import importlib
        import os

        # Find and remove all matchkit .pyc cache files
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(addon_dir, "__pycache__")
        removed   = 0

        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                if f.endswith(".pyc"):
                    try:
                        os.remove(os.path.join(cache_dir, f))
                        removed += 1
                    except Exception:
                        pass

        # Reload all matchkit modules in correct order
        import matchkit
        modules = [
            "matchkit.models",
            "matchkit.operators",
            "matchkit.panels",
            "matchkit",
        ]
        for mod_name in modules:
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception as e:
                    self.report({'WARNING'}, f"Could not reload {mod_name}: {e}")

        # Re-run register
        try:
            bpy.ops.preferences.addon_disable(module="matchkit")
            bpy.ops.preferences.addon_enable(module="matchkit")
            self.report({'INFO'}, f"MatchKit reloaded. Cleared {removed} cache files.")
        except Exception as e:
            self.report({'WARNING'}, f"Reload done but re-register had issue: {e}")

        return {'FINISHED'}


class MATCHKIT_OT_setup_dependencies(bpy.types.Operator):
    """Install required libraries for the selected tracker model"""
    bl_idname  = "matchkit.setup_dependencies"
    bl_label   = "Setup Selected Model"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import importlib
        import subprocess
        import sys

        model_id  = context.scene.matchkit_props.standard_model
        is_hybrid = False
        if context.scene.matchkit_props.tracking_mode == 'HYBRID':
            model_id  = context.scene.matchkit_props.hybrid_model
            is_hybrid = True

        from .models import check_dependencies, get_standard_model, get_hybrid_model
        model   = get_hybrid_model(model_id) if is_hybrid else get_standard_model(model_id)
        all_ok, missing = check_dependencies(model_id, is_hybrid)
        if all_ok:
            self.report({'INFO'}, f"MatchKit: {model['name']} is already installed and ready.")
            return {'FINISHED'}

        for lib in missing:
            pkg = pip_names.get(lib, lib)
            self.report({'INFO'}, f"MatchKit: Installing {pkg}...")
            result = subprocess.call([sys.executable, "-m", "pip", "install", pkg])
            if result != 0:
                self.report({'ERROR'}, f"MatchKit: Failed to install {pkg}. Check your internet connection.")
                return {'CANCELLED'}

        self.report({'INFO'}, f"MatchKit: {model['name']} installed. Restart Blender to activate.")
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  FEATURE 03a — Auto Track (OpenCV)
# ─────────────────────────────────────────────

def run_opencv_tracking(context, frames_to_track, clip, props):
    """Full OpenCV grid-based tracking pipeline"""
    import cv2
    import numpy as np

    footage_path = bpy.path.abspath(clip.filepath)
    footage_dir  = os.path.dirname(footage_path)
    valid_ext    = {'.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff'}

    all_frames = sorted([
        os.path.join(footage_dir, f)
        for f in os.listdir(footage_dir)
        if os.path.splitext(f)[1].lower() in valid_ext
    ])
    if not all_frames:
        return None, f"No image frames found in: {footage_dir}"

    total           = len(all_frames)
    start_idx       = max(0, context.scene.frame_start - 1)
    end_idx         = min(total - 1, context.scene.frame_end - 1)
    frames_to_track = all_frames[start_idx:end_idx + 1]

    if len(frames_to_track) < 2:
        return None, "Need at least 2 frames to track."

    # Read first frame
    first_img = cv2.imread(frames_to_track[0])
    if first_img is None:
        first_img = cv2.imread(frames_to_track[0], cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
    if first_img is None:
        return None, f"Could not read: {frames_to_track[0]}"

    h, w = first_img.shape[:2]
    if first_img.dtype != np.uint8:
        first_img = np.clip(first_img * 255, 0, 255).astype(np.uint8)
    gray_first = cv2.cvtColor(first_img, cv2.COLOR_BGR2GRAY)

    # Get quality preset
    from . models import get_standard_model
    model   = get_standard_model("opencv")
    quality = props.tracker_quality
    preset  = model["quality_presets"][quality]

    max_points      = props.auto_track_max_points
    margin          = props.auto_track_margin
    grid_cols       = props.auto_track_grid_cols
    grid_rows       = props.auto_track_grid_rows
    points_per_cell = max(1, max_points // (grid_cols * grid_rows))
    cell_w          = (w - 2 * margin) // grid_cols
    cell_h          = (h - 2 * margin) // grid_rows

    # Grid-based feature detection
    all_corners = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            x1 = margin + col * cell_w
            y1 = margin + row * cell_h
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            cell_gray = gray_first[y1:y2, x1:x2]
            if cell_gray.size == 0:
                continue
            corners = cv2.goodFeaturesToTrack(
                cell_gray,
                maxCorners   = points_per_cell,
                qualityLevel = preset["qualityLevel"],
                minDistance  = 8,
            )
            if corners is not None:
                for c in corners:
                    all_corners.append([[c[0][0] + x1, c[0][1] + y1]])

    if not all_corners:
        return None, "No trackable features found. Try lowering Quality."

    corners    = np.array(all_corners, dtype=np.float32)
    num_points = len(corners)
    track_data = {i: [(start_idx, corners[i][0][0] / w, corners[i][0][1] / h)]
                  for i in range(num_points)}
    alive      = list(range(num_points))
    gray_prev  = gray_first

    lk_params = dict(
        winSize  = (preset["winSize"], preset["winSize"]),
        maxLevel = preset["maxLevel"],
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    for fi, fpath in enumerate(frames_to_track[1:], start=1):
        img = cv2.imread(fpath)
        if img is None:
            img = cv2.imread(fpath, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        if img is None:
            continue
        if img.dtype != np.uint8:
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        gray_cur = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if not alive:
            break

        pts_prev_arr = np.array(
            [[track_data[i][-1][1] * w, track_data[i][-1][2] * h] for i in alive],
            dtype=np.float32
        ).reshape(-1, 1, 2)

        pts_next, status, _ = cv2.calcOpticalFlowPyrLK(
            gray_prev, gray_cur, pts_prev_arr, None, **lk_params
        )

        still_alive = []
        for i, st, pt in zip(alive, status, pts_next):
            if st[0] == 1:
                nx, ny = pt[0][0], pt[0][1]
                if margin < nx < w - margin and margin < ny < h - margin:
                    track_data[i].append((start_idx + fi, nx / w, ny / h))
                    still_alive.append(i)

        alive     = still_alive
        gray_prev = gray_cur

    min_frames  = max(2, int(len(frames_to_track) * 0.3))
    good_tracks = {i: td for i, td in track_data.items() if len(td) >= min_frames}

    if not good_tracks:
        return None, "No stable tracks found. Try lowering Quality or reducing frame range."

    return good_tracks, None


# ─────────────────────────────────────────────
#  FEATURE 03b — Auto Track (CoTracker3)
# ─────────────────────────────────────────────

def run_cotracker3_tracking(context, clip, props):
    """
    CoTracker3 tracking pipeline — runs on GPU.
    Uses a custom evenly-spaced query grid that respects
    the user's Max Points and Edge Margin settings.
    """
    import torch
    import numpy as np
    import cv2

    footage_path = bpy.path.abspath(clip.filepath)
    footage_dir  = os.path.dirname(footage_path)
    valid_ext    = {'.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff'}

    all_frames = sorted([
        os.path.join(footage_dir, f)
        for f in os.listdir(footage_dir)
        if os.path.splitext(f)[1].lower() in valid_ext
    ])
    if not all_frames:
        return None, f"No image frames found in: {footage_dir}"

    total       = len(all_frames)
    start_idx   = max(0, context.scene.frame_start - 1)
    end_idx     = min(total - 1, context.scene.frame_end - 1)
    frame_paths = all_frames[start_idx:end_idx + 1]

    if len(frame_paths) < 2:
        return None, "Need at least 2 frames to track."

    # Load frames as tensor
    frames = []
    h, w   = None, None
    for fp in frame_paths:
        img = cv2.imread(fp)
        if img is None:
            img = cv2.imread(fp, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        if img is None:
            continue
        if img.dtype != np.uint8:
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if h is None:
            h, w = img.shape[:2]
        frames.append(img)

    if len(frames) < 2:
        return None, "Could not read enough frames."

    device = "cuda" if torch.cuda.is_available() else "cpu"
    video  = torch.from_numpy(np.stack(frames)).permute(0, 3, 1, 2).float()
    video  = video.unsqueeze(0).to(device)  # (1, T, C, H, W)

    # ── Build custom query grid respecting Max Points and Margin ──
    # Instead of CoTracker3's fixed grid_size, we build our own
    # evenly-spaced grid that matches exactly what the user asked for
    max_points = props.auto_track_max_points
    margin     = props.auto_track_margin

    # Calculate grid dimensions that get closest to max_points
    aspect     = w / h
    grid_cols  = max(1, int((max_points * aspect) ** 0.5))
    grid_rows  = max(1, int(max_points / grid_cols))

    # Generate evenly spaced pixel positions within margin
    xs = np.linspace(margin, w - margin, grid_cols)
    ys = np.linspace(margin, h - margin, grid_rows)
    queries = []
    for y in ys:
        for x in xs:
            queries.append([0.0, float(x), float(y)])  # frame 0, x, y in pixels

    queries_tensor = torch.tensor(queries, dtype=torch.float32)
    queries_tensor = queries_tensor.unsqueeze(0).to(device)  # (1, N, 3)

    # Load and run CoTracker3 with our custom query points
    cotracker = torch.hub.load("facebookresearch/co-tracker", "cotracker3_offline")
    cotracker = cotracker.to(device)

    with torch.no_grad():
        pred_tracks, pred_visibility = cotracker(
            video,
            queries = queries_tensor,  # our custom points, not grid_size
        )

    tracks_np     = pred_tracks[0].cpu().numpy()      # (T, N, 2)
    visibility_np = pred_visibility[0].cpu().numpy()  # (T, N)
    num_frames, num_points, _ = tracks_np.shape

    # Convert to MatchKit track format
    good_tracks = {}
    min_frames  = max(2, int(num_frames * 0.3))

    for p in range(num_points):
        point_track = []
        for f in range(num_frames):
            if visibility_np[f, p] > 0.5:
                px = float(tracks_np[f, p, 0]) / w
                py = float(tracks_np[f, p, 1]) / h
                if 0.0 < px < 1.0 and 0.0 < py < 1.0:
                    point_track.append((start_idx + f, px, py))
        if len(point_track) >= min_frames:
            good_tracks[p] = point_track

    if not good_tracks:
        return None, "CoTracker3 found no stable tracks."

    return good_tracks, None



# ─────────────────────────────────────────────
#  TAPNext core tracking — shared by Standard
#  and Hybrid modes
# ─────────────────────────────────────────────

TAPNEXT_WEIGHTS = os.path.join(os.path.expanduser("~"), "tapnet_weights", "bootstapnext_ckpt.npz")

def load_frames_for_tapnext(frame_paths):
    """Load frames as numpy array normalized to 0-1 float32 RGB"""
    import cv2
    import numpy as np
    frames = []
    h, w   = None, None
    for fp in frame_paths:
        img = cv2.imread(fp)
        if img is None:
            img = cv2.imread(fp, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        if img is None:
            continue
        if img.dtype != np.uint8:
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if h is None:
            h, w = img.shape[:2]
        frames.append(img.astype(np.float32) / 255.0)
    return frames, h, w


# TAPNext fixed input size — determined by checkpoint pos_embedding shape
# checkpoint has 1024 patches with patch_size=8 → 32x32 patches → 256x256
TAPNEXT_INPUT_SIZE = 256

def run_tapnext_on_points(frames_np, query_points_xy, h, w):
    """
    Run TAPNext PyTorch on a set of query points.
    Resizes frames to TAPNEXT_INPUT_SIZE to match checkpoint,
    then scales output tracks back to original resolution.
    query_points_xy: list of (x, y) in pixel coords on frame 0
    Returns: good_tracks dict {index: [(frame_idx, nx, ny), ...]}
    """
    import numpy as np
    import torch
    import cv2
    from tapnet.tapnext.tapnext_torch import TAPNext
    from tapnet.tapnext.tapnext_torch_utils import restore_model_from_jax_checkpoint

    device = "cuda" if torch.cuda.is_available() else "cpu"
    sz     = TAPNEXT_INPUT_SIZE

    # ── Letterbox resize: maintain aspect ratio, pad with black ──
    # Squashing to 256x256 distorts coordinates — letterbox instead
    aspect = w / h
    if aspect >= 1.0:
        new_w = sz
        new_h = max(1, int(sz / aspect))
    else:
        new_h = sz
        new_w = max(1, int(sz * aspect))

    pad_x = (sz - new_w) // 2
    pad_y = (sz - new_h) // 2

    frames_resized = []
    for frame in frames_np:
        f8     = (frame * 255).astype(np.uint8) if frame.dtype != np.uint8 else frame
        small  = cv2.resize(f8, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((sz, sz, 3), dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = small
        frames_resized.append(canvas.astype(np.float32) / 255.0)

    # Map query points into letterboxed pixel space
    scale_x = new_w / w
    scale_y = new_h / h
    queries_lb = [(px * scale_x + pad_x, py * scale_y + pad_y)
                  for (px, py) in query_points_xy]

    # Load model
    model = TAPNext(image_size=(sz, sz))
    model = restore_model_from_jax_checkpoint(model, TAPNEXT_WEIGHTS)
    model = model.to(device)
    model.eval()

    video_np   = np.stack(frames_resized, axis=0)
    video      = torch.from_numpy(video_np).unsqueeze(0).to(device)
    num_points = len(queries_lb)
    queries_t  = torch.tensor(
        [[0.0, py / sz, px / sz] for (px, py) in queries_lb],
        dtype=torch.float32
    ).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(video, query_points=queries_t)

    # tracks: (T, N, 2) pixel coords in sz space
    # occlusion: (T, N) raw logits — negative = visible
    tracks_t     = outputs[0][0].cpu().numpy()
    visibility_t = outputs[2][0, :, :, 0].cpu().numpy()

    num_frames  = tracks_t.shape[0]
    good_tracks = {}
    min_frames  = max(2, int(num_frames * 0.3))

    for p in range(num_points):
        point_track = []
        for f in range(num_frames):
            # frame 0 is query frame — always treat as visible
            is_visible = (f == 0) or (visibility_t[f, p] < 0.0)
            if is_visible:
                # Remove letterbox offset and scale back to original 0-1
                ox = (float(tracks_t[f, p, 0]) - pad_x) / new_w
                oy = (float(tracks_t[f, p, 1]) - pad_y) / new_h
                ox = min(max(ox, 0.001), 0.999)
                oy = min(max(oy, 0.001), 0.999)
                point_track.append((f, ox, oy))
        if len(point_track) >= min_frames:
            good_tracks[p] = point_track

    return good_tracks


def get_frame_paths(context, clip):
    """Get sorted frame paths for the current scene frame range"""
    footage_path = bpy.path.abspath(clip.filepath)
    footage_dir  = os.path.dirname(footage_path)
    valid_ext    = {'.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff'}
    all_frames   = sorted([
        os.path.join(footage_dir, f)
        for f in os.listdir(footage_dir)
        if os.path.splitext(f)[1].lower() in valid_ext
    ])
    total       = len(all_frames)
    start_idx   = max(0, context.scene.frame_start - 1)
    end_idx     = min(total - 1, context.scene.frame_end - 1)
    return all_frames[start_idx:end_idx + 1], start_idx


def run_tapnext_standard(context, clip, props):
    """Standard TAPNext — grid of points tracked by TAPNext"""
    import numpy as np
    import cv2

    frame_paths, start_idx = get_frame_paths(context, clip)
    if len(frame_paths) < 2:
        return None, "Need at least 2 frames."

    frames, h, w = load_frames_for_tapnext(frame_paths)
    if len(frames) < 2:
        return None, "Could not read enough frames."

    # Build evenly spaced grid respecting Max Points and Margin
    max_points = props.auto_track_max_points
    margin     = props.auto_track_margin
    aspect     = w / h
    grid_cols  = max(1, int((max_points * aspect) ** 0.5))
    grid_rows  = max(1, int(max_points / grid_cols))
    xs = [margin + (w - 2*margin) * c / max(1, grid_cols-1) for c in range(grid_cols)]
    ys = [margin + (h - 2*margin) * r / max(1, grid_rows-1) for r in range(grid_rows)]
    query_points = [(x, y) for y in ys for x in xs]

    good_tracks = run_tapnext_on_points(frames, query_points, h, w)

    # Offset frame indices to match scene
    offset_tracks = {
        i: [(start_idx + f, nx, ny) for (f, nx, ny) in td]
        for i, td in good_tracks.items()
    }

    if not offset_tracks:
        return None, "TAPNext found no stable tracks."
    return offset_tracks, None


def run_hybrid_opencv_tapnext(context, clip, props):
    """Hybrid: OpenCV detects features, TAPNext tracks them"""
    import cv2, numpy as np

    frame_paths, start_idx = get_frame_paths(context, clip)
    if len(frame_paths) < 2:
        return None, "Need at least 2 frames."

    # Read first frame for OpenCV detection
    first_img = cv2.imread(frame_paths[0])
    if first_img is None:
        first_img = cv2.imread(frame_paths[0], cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
    if first_img is None:
        return None, f"Could not read first frame."

    h, w = first_img.shape[:2]
    if first_img.dtype != np.uint8:
        first_img = np.clip(first_img * 255, 0, 255).astype(np.uint8)
    gray_first = cv2.cvtColor(first_img, cv2.COLOR_BGR2GRAY)

    # OpenCV grid detection
    from .models import get_standard_model
    opencv_model = get_standard_model("opencv")
    quality      = props.hybrid_detection_quality if props.hybrid_quality_mode == 'SPLIT' else props.tracker_quality
    preset       = opencv_model["quality_presets"][quality]
    max_points   = props.auto_track_max_points
    margin       = props.auto_track_margin
    grid_cols    = props.auto_track_grid_cols
    grid_rows    = props.auto_track_grid_rows
    points_per_cell = max(1, max_points // (grid_cols * grid_rows))
    cell_w = (w - 2 * margin) // grid_cols
    cell_h = (h - 2 * margin) // grid_rows

    query_points = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            x1 = margin + col * cell_w
            y1 = margin + row * cell_h
            cell_gray = gray_first[y1:y1+cell_h, x1:x1+cell_w]
            if cell_gray.size == 0:
                continue
            corners = cv2.goodFeaturesToTrack(
                cell_gray,
                maxCorners=points_per_cell,
                qualityLevel=preset["qualityLevel"],
                minDistance=8,
            )
            if corners is not None:
                for c in corners:
                    query_points.append((float(c[0][0] + x1), float(c[0][1] + y1)))

    if not query_points:
        return None, "OpenCV found no trackable features."

    frames, _, _ = load_frames_for_tapnext(frame_paths)
    if len(frames) < 2:
        return None, "Could not read enough frames."

    good_tracks = run_tapnext_on_points(frames, query_points, h, w)
    offset_tracks = {
        i: [(start_idx + f, nx, ny) for (f, nx, ny) in td]
        for i, td in good_tracks.items()
    }
    if not offset_tracks:
        return None, "OpenCV + TAPNext found no stable tracks."
    return offset_tracks, None


def run_hybrid_ensemble(context, clip, props):
    """
    Ensemble: OpenCV detects features, both CoTracker3 and TAPNext track them.
    Per point, keep whichever model had more visible frames (more confident).
    """
    import numpy as np
    import cv2, torch

    frame_paths, start_idx = get_frame_paths(context, clip)
    if len(frame_paths) < 2:
        return None, "Need at least 2 frames."

    # ── OpenCV detection (shared for both models) ──
    first_img = cv2.imread(frame_paths[0])
    if first_img is None:
        first_img = cv2.imread(frame_paths[0], cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
    if first_img is None:
        return None, "Could not read first frame."
    h, w = first_img.shape[:2]
    if first_img.dtype != np.uint8:
        first_img = np.clip(first_img * 255, 0, 255).astype(np.uint8)
    gray_first = cv2.cvtColor(first_img, cv2.COLOR_BGR2GRAY)

    from .models import get_standard_model
    opencv_model = get_standard_model("opencv")
    quality      = props.tracker_quality
    preset       = opencv_model["quality_presets"][quality]
    max_points   = props.auto_track_max_points
    margin       = props.auto_track_margin
    grid_cols    = props.auto_track_grid_cols
    grid_rows    = props.auto_track_grid_rows
    points_per_cell = max(1, max_points // (grid_cols * grid_rows))
    cell_w = (w - 2 * margin) // grid_cols
    cell_h = (h - 2 * margin) // grid_rows

    query_points = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            x1 = margin + col * cell_w
            y1 = margin + row * cell_h
            cell_gray = gray_first[y1:y1+cell_h, x1:x1+cell_w]
            if cell_gray.size == 0:
                continue
            corners = cv2.goodFeaturesToTrack(
                cell_gray,
                maxCorners=points_per_cell,
                qualityLevel=preset["qualityLevel"],
                minDistance=8,
            )
            if corners is not None:
                for c in corners:
                    query_points.append((float(c[0][0] + x1), float(c[0][1] + y1)))

    if not query_points:
        return None, "OpenCV found no trackable features."

    num_qp = len(query_points)

    # ── Pass 1: CoTracker3 ──
    device = "cuda" if torch.cuda.is_available() else "cpu"
    frames_cv = []
    for fp in frame_paths:
        img = cv2.imread(fp)
        if img is None:
            img = cv2.imread(fp, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        if img is None:
            continue
        if img.dtype != np.uint8:
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        frames_cv.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    video = torch.from_numpy(np.stack(frames_cv)).permute(0,3,1,2).float().unsqueeze(0).to(device)
    queries_ct3 = torch.tensor(
        [[0.0, px, py] for (px, py) in query_points],
        dtype=torch.float32
    ).unsqueeze(0).to(device)

    cotracker = torch.hub.load("facebookresearch/co-tracker", "cotracker3_offline")
    cotracker  = cotracker.to(device)
    with torch.no_grad():
        ct3_tracks, ct3_vis = cotracker(video, queries=queries_ct3)
    ct3_tracks = ct3_tracks[0].cpu().numpy()  # (T, N, 2)
    ct3_vis    = ct3_vis[0].cpu().numpy()     # (T, N)

    # ── Pass 2: TAPNext ──
    frames_tap, _, _ = load_frames_for_tapnext(frame_paths)
    tap_tracks_raw   = run_tapnext_on_points(frames_tap, query_points, h, w)

    # ── Merge: per point keep whichever model had more confident frames ──
    num_frames  = ct3_tracks.shape[0]
    min_frames  = max(2, int(num_frames * 0.3))
    good_tracks = {}

    for p in range(num_qp):
        # CoTracker3 track for this point
        ct3_point = []
        for f in range(num_frames):
            if ct3_vis[f, p] > 0.5:
                nx = float(ct3_tracks[f, p, 0]) / w
                ny = float(ct3_tracks[f, p, 1]) / h
                if 0.0 < nx < 1.0 and 0.0 < ny < 1.0:
                    ct3_point.append((start_idx + f, nx, ny))

        # TAPNext track for this point
        tap_point = [(start_idx + f, nx, ny) for (f, nx, ny) in tap_tracks_raw.get(p, [])]

        # Keep whichever survived more frames
        if len(ct3_point) >= len(tap_point):
            best = ct3_point
        else:
            best = tap_point

        if len(best) >= min_frames:
            good_tracks[p] = best

    if not good_tracks:
        return None, "Ensemble found no stable tracks."
    return good_tracks, None

# ─────────────────────────────────────────────
#  FEATURE 03 — Auto Track Operator (dispatcher)
# ─────────────────────────────────────────────

class MATCHKIT_OT_auto_track(bpy.types.Operator):
    """Auto track footage using the selected AI/CV tracker model"""
    bl_idname  = "matchkit.auto_track"
    bl_label   = "Auto Track"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        from .models import check_dependencies
        clip  = context.edit_movieclip
        if not clip:
            return False
        props = context.scene.matchkit_props
        if props.tracking_mode == 'HYBRID':
            all_ok, _ = check_dependencies(props.hybrid_model, is_hybrid=True)
        else:
            all_ok, _ = check_dependencies(props.standard_model, is_hybrid=False)
        return all_ok

    def execute(self, context):
        props = context.scene.matchkit_props
        clip  = context.edit_movieclip

        # Dispatch based on mode
        if props.tracking_mode == 'HYBRID':
            model_id = props.hybrid_model
            if model_id == "hybrid_opencv_ct3":
                good_tracks, error = run_hybrid_tracking(context, clip, props)
            elif model_id == "hybrid_opencv_tapnext":
                good_tracks, error = run_hybrid_opencv_tapnext(context, clip, props)
            elif model_id == "hybrid_ensemble":
                good_tracks, error = run_hybrid_ensemble(context, clip, props)
            else:
                self.report({'ERROR'}, f"Hybrid model '{model_id}' not implemented yet.")
                return {'CANCELLED'}
        else:
            model_id = props.standard_model
            if model_id == "opencv":
                good_tracks, error = run_opencv_tracking(context, None, clip, props)
            elif model_id == "cotracker3":
                good_tracks, error = run_cotracker3_tracking(context, clip, props)
            elif model_id == "tapnext":
                good_tracks, error = run_tapnext_standard(context, clip, props)
            else:
                self.report({'ERROR'}, f"Model '{model_id}' not implemented yet.")
                return {'CANCELLED'}

        if error:
            self.report({'WARNING'}, f"MatchKit: {error}")
            return {'CANCELLED'}

        # Inject all tracks into Blender as real markers
        tracking = clip.tracking
        injected = 0

        for i, frames_list in good_tracks.items():
            prefix     = {"opencv": "OCV", "cotracker3": "CT3", "tapnext": "TAP", "hybrid_opencv_ct3": "HCT", "hybrid_opencv_tapnext": "HTP", "hybrid_ensemble": "ENS"}.get(model_id, "MK")
            track_name = f"MK_{prefix}_{i:03d}"
            new_track  = tracking.tracks.new(name=track_name, frame=frames_list[0][0] + 1)
            for (frame_idx, nx, ny) in frames_list:
                blender_y      = 1.0 - ny  # flip Y: top-left → bottom-left
                marker         = new_track.markers.insert_frame(frame_idx + 1)
                marker.co      = (nx, blender_y)
                marker.mute    = False
            injected += 1

        self.report({'INFO'}, f"MatchKit: Injected {injected} stable tracks. Review and solve!")
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Addon Properties
# ─────────────────────────────────────────────

def get_standard_items(self, context):
    from . models import get_standard_enum_items
    return get_standard_enum_items()

def get_hybrid_items(self, context):
    from . models import get_hybrid_enum_items
    return get_hybrid_enum_items()


class MatchKitProperties(bpy.types.PropertyGroup):

    # ── Tracking Mode ──
    tracking_mode: bpy.props.EnumProperty(
        name        = "Mode",
        description = "Standard uses one model. Hybrid combines two models for better results.",
        items       = [
            ('STANDARD', "Standard", "Use a single tracker model"),
            ('HYBRID',   "Hybrid",   "Combine two models — OpenCV finds features, AI tracks them"),
        ],
        default     = 'STANDARD',
    )

    # ── Standard model selector ──
    standard_model: bpy.props.EnumProperty(
        name        = "Tracker Engine",
        description = "Which tracking model to use in Standard mode",
        items       = get_standard_items,
        default     = 0,
    )

    # ── Hybrid model selector ──
    hybrid_model: bpy.props.EnumProperty(
        name        = "Hybrid Model",
        description = "Which hybrid combination to use",
        items       = get_hybrid_items,
        default     = 0,
    )

    # ── Shared settings ──
    tracker_quality: bpy.props.EnumProperty(
        name        = "Quality",
        description = "Speed vs accuracy tradeoff — applies to both detection and tracking",
        items       = [
            ('FAST',     "Fast",     "Quicker, good for testing"),
            ('BALANCED', "Balanced", "Recommended for most shots"),
            ('BEST',     "Best",     "Slowest but most accurate"),
        ],
        default     = 'BALANCED',
    )
    hybrid_quality_mode: bpy.props.EnumProperty(
        name        = "Quality Mode",
        description = "Control detection and tracking quality together or separately",
        items       = [
            ('LINKED', "Linked", "One quality setting controls both detection and tracking"),
            ('SPLIT',  "Split",  "Set detection and tracking quality independently"),
        ],
        default     = 'LINKED',
    )
    hybrid_detection_quality: bpy.props.EnumProperty(
        name        = "Detection Quality",
        description = "Quality for OpenCV feature detection step",
        items       = [
            ('FAST',     "Fast",     "Quicker, good for testing"),
            ('BALANCED', "Balanced", "Recommended for most shots"),
            ('BEST',     "Best",     "Slowest but most accurate"),
        ],
        default     = 'BALANCED',
    )
    hybrid_tracking_quality: bpy.props.EnumProperty(
        name        = "Tracking Quality",
        description = "Quality for CoTracker3 AI tracking step",
        items       = [
            ('FAST',     "Fast",     "Quicker, good for testing"),
            ('BALANCED', "Balanced", "Recommended for most shots"),
            ('BEST',     "Best",     "Slowest but most accurate"),
        ],
        default     = 'BALANCED',
    )
    auto_track_max_points: bpy.props.IntProperty(
        name        = "Max Points",
        description = "Total number of tracking points",
        default     = 80, min = 10, max = 500,
    )
    auto_track_margin: bpy.props.IntProperty(
        name        = "Edge Margin (px)",
        description = "Ignore features this many pixels from the frame edge",
        default     = 20, min = 0, max = 200,
    )
    auto_track_grid_cols: bpy.props.IntProperty(
        name        = "Grid Columns",
        description = "Frame grid columns for even feature spread",
        default     = 4, min = 1, max = 10,
    )
    auto_track_grid_rows: bpy.props.IntProperty(
        name        = "Grid Rows",
        description = "Frame grid rows for even feature spread",
        default     = 4, min = 1, max = 10,
    )


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = [
    MatchKitProperties,
    MATCHKIT_OT_camera_triangulate,
    MATCHKIT_OT_sync_selection,
    MATCHKIT_OT_select_bad_tracks,
    MATCHKIT_OT_switch_to_graph,
    MATCHKIT_OT_reload,
    MATCHKIT_OT_switch_to_clip,
    MATCHKIT_OT_setup_dependencies,
    MATCHKIT_OT_auto_track,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.matchkit_props = bpy.props.PointerProperty(type=MatchKitProperties)

def unregister():
    del bpy.types.Scene.matchkit_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


# ─────────────────────────────────────────────
#  FEATURE 03c — Hybrid Tracking
#  OpenCV detects features → CoTracker3 tracks
# ─────────────────────────────────────────────

def run_hybrid_tracking(context, clip, props):
    """
    Hybrid pipeline:
    1. OpenCV grid finds the best feature points on frame 1
    2. Those exact points are passed to CoTracker3 as queries
    3. CoTracker3 tracks them with full AI quality
    """
    import cv2
    import numpy as np
    import torch
    from .models import get_hybrid_model

    footage_path = bpy.path.abspath(clip.filepath)
    footage_dir  = os.path.dirname(footage_path)
    valid_ext    = {'.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff'}

    all_frames = sorted([
        os.path.join(footage_dir, f)
        for f in os.listdir(footage_dir)
        if os.path.splitext(f)[1].lower() in valid_ext
    ])
    if not all_frames:
        return None, f"No image frames found in: {footage_dir}"

    total       = len(all_frames)
    start_idx   = max(0, context.scene.frame_start - 1)
    end_idx     = min(total - 1, context.scene.frame_end - 1)
    frame_paths = all_frames[start_idx:end_idx + 1]

    if len(frame_paths) < 2:
        return None, "Need at least 2 frames to track."

    # ── Step 1: Read first frame ──
    first_img = cv2.imread(frame_paths[0])
    if first_img is None:
        first_img = cv2.imread(frame_paths[0], cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
    if first_img is None:
        return None, f"Could not read first frame: {frame_paths[0]}"

    h, w = first_img.shape[:2]
    if first_img.dtype != np.uint8:
        first_img = np.clip(first_img * 255, 0, 255).astype(np.uint8)
    gray_first = cv2.cvtColor(first_img, cv2.COLOR_BGR2GRAY)

    # ── Step 2: OpenCV grid feature detection ──
    # Resolve which quality to use for detection
    from .models import get_standard_model
    opencv_model     = get_standard_model("opencv")
    if props.hybrid_quality_mode == 'SPLIT':
        detect_quality = props.hybrid_detection_quality
    else:
        detect_quality = props.tracker_quality
    preset = opencv_model["quality_presets"][detect_quality]
    max_points  = props.auto_track_max_points
    margin      = props.auto_track_margin
    grid_cols   = props.auto_track_grid_cols
    grid_rows   = props.auto_track_grid_rows
    points_per_cell = max(1, max_points // (grid_cols * grid_rows))
    cell_w      = (w - 2 * margin) // grid_cols
    cell_h      = (h - 2 * margin) // grid_rows

    all_corners = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            x1 = margin + col * cell_w
            y1 = margin + row * cell_h
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            cell_gray = gray_first[y1:y2, x1:x2]
            if cell_gray.size == 0:
                continue
            corners = cv2.goodFeaturesToTrack(
                cell_gray,
                maxCorners   = points_per_cell,
                qualityLevel = preset["qualityLevel"],
                minDistance  = 8,
            )
            if corners is not None:
                for c in corners:
                    px = float(c[0][0] + x1)
                    py = float(c[0][1] + y1)
                    all_corners.append([px, py])

    if not all_corners:
        return None, "OpenCV found no trackable features. Try lowering Quality."

    # ── Step 3: Load all frames as tensor for CoTracker3 ──
    frames = []
    for fp in frame_paths:
        img = cv2.imread(fp)
        if img is None:
            img = cv2.imread(fp, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        if img is None:
            continue
        if img.dtype != np.uint8:
            img = np.clip(img * 255, 0, 255).astype(np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        frames.append(img)

    if len(frames) < 2:
        return None, "Could not read enough frames."

    device = "cuda" if torch.cuda.is_available() else "cpu"
    video  = torch.from_numpy(np.stack(frames)).permute(0, 3, 1, 2).float()
    video  = video.unsqueeze(0).to(device)  # (1, T, C, H, W)

    # ── Step 4: Build query points tensor for CoTracker3 ──
    # CoTracker3 query format: (frame_index, x, y) — frame 0, pixel coordinates
    queries = []
    for (px, py) in all_corners:
        queries.append([0.0, px, py])  # frame 0, x, y in pixels

    queries_tensor = torch.tensor(queries, dtype=torch.float32)
    queries_tensor = queries_tensor.unsqueeze(0).to(device)  # (1, N, 3)

    # ── Step 5: CoTracker3 tracks the OpenCV points ──
    cotracker = torch.hub.load("facebookresearch/co-tracker", "cotracker3_offline")
    cotracker = cotracker.to(device)

    with torch.no_grad():
        pred_tracks, pred_visibility = cotracker(
            video,
            queries = queries_tensor,
        )

    # pred_tracks:     (1, T, N, 2)
    # pred_visibility: (1, T, N)
    tracks_np     = pred_tracks[0].cpu().numpy()
    visibility_np = pred_visibility[0].cpu().numpy()

    num_frames, num_points, _ = tracks_np.shape

    # ── Step 6: Convert to MatchKit track format ──
    good_tracks = {}
    min_frames  = max(2, int(num_frames * 0.3))

    for p in range(num_points):
        point_track = []
        for f in range(num_frames):
            if visibility_np[f, p] > 0.5:
                px = float(tracks_np[f, p, 0]) / w
                py = float(tracks_np[f, p, 1]) / h
                # Keep only points that stay within frame bounds
                if 0.0 < px < 1.0 and 0.0 < py < 1.0:
                    point_track.append((start_idx + f, px, py))
        if len(point_track) >= min_frames:
            good_tracks[p] = point_track

    if not good_tracks:
        return None, "Hybrid tracking found no stable tracks. Try lowering Quality."

    return good_tracks, None
