// Draws the app icon of Prey2006 (a glowing portal ring, no artwork of the game).
// Usage: swift make_icon.swift <output.png> [size]

import AppKit
import CoreGraphics

let args = CommandLine.arguments
guard args.count >= 2 else {
	FileHandle.standardError.write("usage: make_icon.swift <output.png> [size]\n".data(using: .utf8)!)
	exit(1)
}
let size = args.count >= 3 ? Int(args[2])! : 1024
let s = CGFloat(size)

let space = CGColorSpace(name: CGColorSpace.sRGB)!
let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: 0,
	space: space, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
	return CGColor(colorSpace: space, components: [r, g, b, a])!
}

// rounded square background (macOS icon grid: 824/1024 with ~185 corner radius)
let inset = s * 100 / 1024
let rect = CGRect(x: inset, y: inset, width: s - 2 * inset, height: s - 2 * inset)
let shape = CGPath(roundedRect: rect, cornerWidth: s * 185 / 1024, cornerHeight: s * 185 / 1024, transform: nil)
ctx.saveGState()
ctx.addPath(shape)
ctx.clip()
let bg = CGGradient(colorsSpace: space, colors: [color(0.10, 0.04, 0.03), color(0.02, 0.02, 0.04)] as CFArray, locations: [0, 1])!
ctx.drawLinearGradient(bg, start: CGPoint(x: 0, y: s), end: CGPoint(x: 0, y: 0), options: [])

let center = CGPoint(x: s / 2, y: s / 2)
let radius = s * 0.27

// glow inside the portal
let inner = CGGradient(colorsSpace: space,
	colors: [color(1.0, 0.75, 0.35, 0.55), color(0.9, 0.3, 0.05, 0.15), color(0.5, 0.1, 0.0, 0)] as CFArray,
	locations: [0, 0.6, 1])!
ctx.drawRadialGradient(inner, startCenter: center, startRadius: 0, endCenter: center, endRadius: radius * 1.05, options: [])

// the ring, drawn several times for a glow
for (width, alpha) in [(0.16, 0.10), (0.10, 0.18), (0.06, 0.35), (0.035, 0.9)] as [(CGFloat, CGFloat)] {
	ctx.setStrokeColor(color(1.0, 0.55, 0.15, alpha))
	ctx.setLineWidth(s * width)
	ctx.strokeEllipse(in: CGRect(x: center.x - radius, y: center.y - radius, width: 2 * radius, height: 2 * radius))
}
ctx.setStrokeColor(color(1.0, 0.92, 0.75, 1))
ctx.setLineWidth(s * 0.012)
ctx.strokeEllipse(in: CGRect(x: center.x - radius, y: center.y - radius, width: 2 * radius, height: 2 * radius))
ctx.restoreGState()

let image = ctx.makeImage()!
let rep = NSBitmapImageRep(cgImage: image)
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[1]))
