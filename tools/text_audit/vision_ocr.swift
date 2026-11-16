// Apple Vision OCR helper. Usage: vision_ocr <image> [<image> ...]  -> JSON lines, one per image:
// {"image":..., "seconds":..., "lines":[{"t":text,"x":minX,"y":minY(top-origin),"w":..,"h":..,"c":conf}]}  coords normalised 0..1, y from TOP.
import Foundation
import Vision
import AppKit

func run(_ path: String) {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("{\"image\":\"\(path)\",\"error\":\"load\"}"); return
    }
    let t0 = Date()
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    req.recognitionLanguages = ["en-US"]
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([req])
    var lines: [[String: Any]] = []
    for o in (req.results ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        lines.append(["t": c.string, "x": b.minX, "y": 1.0 - b.maxY, "w": b.width, "h": b.height, "c": c.confidence])
    }
    let out: [String: Any] = ["image": path, "seconds": Date().timeIntervalSince(t0), "lines": lines]
    let data = try! JSONSerialization.data(withJSONObject: out, options: [])
    print(String(data: data, encoding: .utf8)!)
}
for a in CommandLine.arguments.dropFirst() { run(a) }
