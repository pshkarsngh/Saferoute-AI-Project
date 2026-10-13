# SafeRoute AI — Preprocessing Pipeline Documentation

**Pipeline Version:** `preprocess-v1`  
**Governing rules:** `master_rules.md` Rule 6, `TRD.md` §7, `ARCHITECTURE.md` §6

## 1. Overview
The `src.preprocessing` module defines the single, versioned, and documented OpenCV preprocessing and validation pipeline for the SafeRoute AI project. It ensures that input images are safely validated, deterministically resized and normalized for YOLO11 inference, and visualised without modifying the source files.

## 2. API Contract
The module exposes the following core functions:
- `validate_image(path_or_bytes) -> ImageStatus`: Checks for existence, decodability, corruption, channel count, and minimum dimension thresholds. Returns an explicit structured dataclass (`ImageStatus`) with failure categorization (`ok`, `empty`, `unreadable`, `corrupt`, `unsupported`, `too_small`).
- `preprocess(image: np.ndarray) -> PreparedImage`: Applies deterministic aspect-ratio preserving letterboxing to target shape (`640x640`). Works strictly on a copy.
- `prepare_inference_input(image: np.ndarray) -> Tuple[np.ndarray, PreparedImage]`: Normalizes letterboxed images to RGB CHW float32 `[0.0, 1.0]` tensor format for YOLO11 inference.
- `visualise(image, detections, output_path=None) -> np.ndarray`: Draws detection bounding boxes and labels onto an image copy.

## 3. Implemented Transforms & Rationales
1. **Letterbox Resizing (`letterbox`)**:
   - *Rationale:* YOLO models require fixed-dimension inputs (e.g. 640x640). Direct resizing without padding causes severe aspect-ratio distortion, skewing road hazard shapes (e.g. stretching cracks and distorting potholes). Letterboxing preserves the aspect ratio with neutral grey padding (`114, 114, 114`).
2. **Channel & Color Management**:
   - *Rationale:* OpenCV default I/O uses BGR. BGR is preserved for OpenCV operations and converted to RGB only when preparing inputs for neural network inference.
3. **Optional Enhancements (CLAHE)**:
   - *Rationale:* CLAHE is **disabled by default** per Rule 6 and TRD §7.1. It can be toggled via `config/preprocessing.yaml` if future empirical evaluation proves it enhances detection accuracy under varied illumination.
4. **Non-Destructive Operations**:
   - *Rationale:* Per Rule 1 and Rule 19, source datasets and images must never be overwritten or mutated. All transformations and visualisations operate strictly on array copies.

## 4. Configuration
Parameters are loaded dynamically from [`config/preprocessing.yaml`](file:///d:/New%20folder%20(3)/config/preprocessing.yaml).
