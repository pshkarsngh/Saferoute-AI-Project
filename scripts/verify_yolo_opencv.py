#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""SafeRoute AI - YOLO11 + OpenCV functional verification (READ-ONLY).

Does NOT retrain, overwrite checkpoints, or modify datasets. Produces machine
evidence to reports/phase21_yolo_opencv/evidence.json and prints a summary.

Run:  .\.venv\Scripts\python.exe scripts\verify_yolo_opencv.py
"""

import os, sys, json, glob, hashlib, traceback
from datetime import datetime, timezone

WS = r"D:\New folder (3)"
if WS not in sys.path:
    sys.path.insert(0, WS)

OUT_DIR = os.path.join(WS, "reports", "phase21_yolo_opencv")
IMG_DIR = os.path.join(WS, "data", "pothole_crack_manhole", "data", "images")
LBL_DIR = os.path.join(WS, "data", "pothole_crack_manhole", "data", "labels-YOLO")
V1 = os.path.join(WS, "models", "training", "saferoute-yolo11-v1", "weights", "best.pt")
V2 = os.path.join(WS, "models", "training", "saferoute-yolo11-v2", "weights", "best.pt")

E = {"generated_utc": datetime.now(timezone.utc).isoformat(), "sections": {}}


def rec(name, **kw):
    E["sections"][name] = kw
    print(f"[{name}] " + json.dumps(kw, default=str)[:800], flush=True)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


def opencv_checks():
    import cv2, numpy as np
    from src.preprocessing.pipeline import PreprocessingPipeline, ImageStatusCode
    s = {"opencv_version": cv2.__version__, "numpy_version": np.__version__}
    img_path = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))[0]
    s["sample_image"] = img_path
    bgr = cv2.imread(img_path)
    s["imread_ok"] = bgr is not None
    s["original_shape_hwc"] = list(bgr.shape)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    s["color_conversion_ok"] = (rgb.shape == bgr.shape) and not np.array_equal(rgb, bgr)
    resized = cv2.resize(bgr, (320, 320))
    s["resize_ok"] = list(resized.shape) == [320, 320, 3]
    pipe = PreprocessingPipeline()
    prep = pipe.preprocess(bgr)
    s["letterbox_shape"] = list(prep.image.shape)
    s["target_shape"] = list(prep.target_shape)
    s["ratio"] = list(prep.ratio)
    s["pad"] = list(prep.pad)
    s["pipeline_version"] = pipe.version
    vstatus = pipe.validate_image(img_path)
    s["validate_real_ok"] = [vstatus.code.value, vstatus.is_valid, vstatus.width, vstatus.height]
    # negative controls
    tmp = os.path.join(OUT_DIR, "_tmp"); os.makedirs(tmp, exist_ok=True)
    empty = os.path.join(tmp, "empty.jpg"); open(empty, "wb").close()
    s["validate_empty"] = pipe.validate_image(empty).code.value
    small = os.path.join(tmp, "small.png")
    cv2.imwrite(small, np.zeros((16, 16, 3), dtype=np.uint8))
    s["validate_too_small"] = pipe.validate_image(small).code.value
    s["validate_missing"] = pipe.validate_image(os.path.join(tmp, "nope.jpg")).code.value
    tensor, prepared = pipe.prepare_inference_input(bgr)
    s["inference_tensor_shape"] = list(tensor.shape)
    s["inference_tensor_dtype"] = str(tensor.dtype)
    s["inference_tensor_range"] = [float(tensor.min()), float(tensor.max())]
    # drawing
    from src.preprocessing.pipeline import DetectionBox
    canvas = pipe.visualise(bgr, [DetectionBox("pothole", 0.9, (10, 10, 100, 100))],
                            os.path.join(tmp, "vis.jpg"))
    s["draw_returns_copy"] = (canvas is not None and canvas.shape == bgr.shape)
    s["draw_output_exists"] = os.path.isfile(os.path.join(tmp, "vis.jpg"))
    rec("opencv", **s)
    return s


def detector_checks():
    import numpy as np
    from src.detection.detector import HazardDetector
    s = {}
    det = HazardDetector(device="cpu")
    s["checkpoint_path"] = str(det.checkpoint_path)
    s["checkpoint_sha256"] = sha256(str(det.checkpoint_path))
    s["model_version"] = det.model_version
    s["detector_version"] = det.detector_version
    s["imgsz"] = det.imgsz
    s["conf_threshold"] = det.conf_threshold
    s["iou_threshold"] = det.iou_threshold
    s["max_det"] = det.max_det
    from src.detection.detector import SUPPORTED_CLASSES
    s["supported_classes"] = SUPPORTED_CLASSES
    s["model_classes"] = dict(getattr(det.model, "names", {}))

    samples = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))[:8]
    results = []
    for p in samples:
        r = det.detect(p, image_id=os.path.basename(p))
        results.append({
            "image": os.path.basename(p), "status": r.status.value,
            "n": len(r.detections), "dims": [r.image_width, r.image_height],
            "dets": [{"cls": d.hazard_class, "conf": round(d.confidence, 4),
                      "bbox": [round(v, 1) for v in d.bbox_xyxy],
                      "norm": [round(v, 4) for v in d.bbox_norm]} for d in r.detections],
        })
    s["positive_samples"] = results
    blank = np.full((480, 640, 3), 128, dtype=np.uint8)
    rb = det.detect(blank, image_id="blank_negative", conf=0.15)
    s["blank_negative"] = {"status": rb.status.value, "n": len(rb.detections)}
    rec("detector", **s)
    return s, det


def threshold_and_pipeline(det):
    from src.risk.aggregate import HazardAggregator
    from src.risk.severity import SeverityPolicy
    from src.risk.engine import DeterministicRiskEngine
    s = {}
    policy = SeverityPolicy()
    agg = HazardAggregator(policy)
    s["detector_conf_threshold"] = det.conf_threshold
    s["aggregator_confidence_threshold"] = policy.confidence_threshold
    s["thresholds_consistent"] = (det.conf_threshold == policy.confidence_threshold)

    samples = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))[:15]
    raw_total = dropped = kept = 0
    raw_confs = []
    for p in samples:
        r = det.detect(p)
        for d in r.detections:
            raw_total += 1
            raw_confs.append(round(d.confidence, 4))
            if d.confidence < policy.confidence_threshold:
                dropped += 1
            else:
                kept += 1
    s["sample_images"] = len(samples)
    s["raw_detections_at_detector_conf"] = raw_total
    s["detections_dropped_by_aggregator"] = dropped
    s["detections_kept_by_aggregator"] = kept
    s["raw_conf_min_max"] = [min(raw_confs), max(raw_confs)] if raw_confs else None

    # pipeline trace: one positive image
    pos = samples[0]
    r = det.detect(pos)
    asm = agg.assess_segment("seg-trace-0000", [r], expected_image_count=1, route_id="rt-trace")
    engine = DeterministicRiskEngine()
    route = engine.score_route("rt-trace", [asm], [200.0])
    s["trace_positive"] = {
        "image": os.path.basename(pos), "detector_status": r.status.value,
        "raw_dets": len(r.detections),
        "segment_hazards": len(asm.hazards), "aggregate_hazard": asm.aggregate_hazard,
        "segment_status": asm.status.value, "coverage": asm.coverage.fraction,
        "route_score": route.route_score, "route_status": route.status.value,
    }
    # zero-detection case
    import numpy as np
    rb = det.detect(np.full((480, 640, 3), 128, dtype=np.uint8))
    asm0 = agg.assess_segment("seg-zero-0000", [rb], expected_image_count=1, route_id="rt-zero")
    route0 = engine.score_route("rt-zero", [asm0], [200.0])
    s["trace_zero_detection"] = {
        "segment_hazards": len(asm0.hazards), "aggregate_hazard": asm0.aggregate_hazard,
        "segment_status": asm0.status.value, "coverage": asm0.coverage.fraction,
        "route_score": route0.route_score, "route_status": route0.status.value,
    }
    rec("thresholds_and_pipeline", **s)
    return s


def _iou(a, b):
    xa, ya = max(a[0], b[0]), max(a[1], b[1])
    xb, yb = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, xb - xa), max(0.0, yb - ya)
    inter = iw * ih
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def _load_gt(stem, W, H):
    gt = []
    p = os.path.join(LBL_DIR, stem + ".txt")
    if not os.path.isfile(p):
        return gt
    with open(p) as f:
        for line in f:
            parts = line.split()
            if len(parts) != 5:
                continue
            cid = int(float(parts[0]))
            if cid not in (0, 1):
                continue
            cx, cy, w, h = (float(x) for x in parts[1:])
            gt.append((cid, [(cx-w/2)*W, (cy-h/2)*H, (cx+w/2)*W, (cy+h/2)*H]))
    return gt


def labelled_eval(det, conf, n=40):
    from pathlib import Path
    split = os.path.join(WS, "data", "splits", "test.txt")
    paths = [Path(l.strip()) for l in open(split) if l.strip()][:n]
    cname = {0: "pothole", 1: "crack"}
    tp = fp = fn = 0
    per = {0: [0, 0, 0], 1: [0, 0, 0]}
    used = 0
    for p in paths:
        if not p.is_file():
            continue
        used += 1
        stem = p.stem
        r = det.detect(str(p), conf=conf)
        W, H = r.image_width, r.image_height
        gt = _load_gt(stem, W, H)
        preds = []
        for d in r.detections:
            cid = 0 if d.hazard_class == "pothole" else (1 if d.hazard_class == "crack" else None)
            if cid is not None:
                preds.append((cid, d.confidence, d.bbox_xyxy))
        preds.sort(key=lambda x: x[1], reverse=True)
        matched = set()
        for cid, confv, box in preds:
            best, bi = 0.5, -1
            for i, (gcid, gbox) in enumerate(gt):
                if i in matched or gcid != cid:
                    continue
                iou = _iou(box, gbox)
                if iou > best:
                    best, bi = iou, i
            if bi >= 0:
                matched.add(bi); tp += 1; per[cid][0] += 1
            else:
                fp += 1; per[cid][1] += 1
        for i, (gcid, _g) in enumerate(gt):
            if i not in matched:
                fn += 1; per[gcid][2] += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "split": "test.txt", "images_evaluated": used, "conf_threshold": conf,
        "iou_match": 0.5, "TP": tp, "FP": fp, "FN": fn,
        "precision": round(prec, 4), "recall": round(recall, 4),
        "per_class": {cname[c]: {"TP": per[c][0], "FP": per[c][1], "FN": per[c][2]} for c in (0, 1)},
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        opencv_checks()
        d, det = detector_checks()
        threshold_and_pipeline(det)
        E["sections"]["labelled_eval_conf_0.15"] = labelled_eval(det, 0.15, 40)
        E["sections"]["labelled_eval_conf_0.25"] = labelled_eval(det, 0.25, 40)
    except Exception:
        E["error"] = traceback.format_exc()
        print(E["error"])
    out = os.path.join(OUT_DIR, "evidence.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(E, f, indent=2, default=str)
    print("WROTE", out)


if __name__ == "__main__":
    main()





