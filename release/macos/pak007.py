#!/usr/bin/env python3
"""
Tools for releasing pak007.pk4 without the files of the retail game.

pak007.pk4 (built from base/) holds the port's widescreen HUD, menus and other
fixed assets, but most of these files are modified copies of the retail files
in pak000.pk4. Releases must not contain them, so they ship as binary patches
(BSDIFF40, applied with the bspatch of macOS) against the files of the player's
own copy of the game, see install_assets.sh.

pak007.manifest says which files of base/ go into the release:
	copy  <path>            the file is shipped as it is (own work of the port)
	copy  <path> <source>   same, but taken from <source> (relative to the repo)
	patch <path>            only a patch from the retail file to base/<path> is shipped
Everything else in base/ is not released (see the "extras" command).

Commands:
	payload  build the release payload (files, patches, pak007.list)
	extras   pack the files of base/ that are not released into a pk4
	verify   check that a directory doesn't contain files of the retail game
"""

import argparse
import bz2
import difflib
import glob
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

RETAIL_PAKS = ['pak000.pk4', 'pak001.pk4', 'pak002.pk4', 'pak003.pk4', 'pak004.pk4']


def md5(data):
	return hashlib.md5(data).hexdigest()


def read_manifest(path):
	entries = []
	with open(path) as f:
		for num, line in enumerate(f, 1):
			line = line.split('#', 1)[0].strip()
			if not line:
				continue
			parts = line.split()
			if parts[0] not in ('copy', 'patch') or len(parts) not in (2, 3) or (parts[0] == 'patch' and len(parts) != 2):
				sys.exit('%s:%d: invalid line: %s' % (path, num, line))
			entries.append((parts[0], parts[1], parts[2] if len(parts) == 3 else None))
	return entries


class RetailGame:
	"""The retail pk4s, searched like the game does (later paks override earlier ones)."""

	def __init__(self, base_dir):
		self.paks = []
		for name in RETAIL_PAKS:
			path = os.path.join(base_dir, name)
			if not os.path.isfile(path):
				sys.exit('retail pk4 not found: %s' % path)
			self.paks.append((name, zipfile.ZipFile(path)))
		self.index = {}
		for name, z in self.paks:
			for info in z.infolist():
				if not info.is_dir():
					self.index[info.filename.lower()] = (name, z, info)

	def read(self, path):
		hit = self.index.get(path.lower())
		if not hit:
			return None, None
		name, z, info = hit
		return name, z.read(info)

	def all_hashes(self):
		hashes = {}
		for name, z in self.paks:
			for info in z.infolist():
				if not info.is_dir() and info.file_size > 0:
					hashes.setdefault(md5(z.read(info)), '%s:%s' % (name, info.filename))
		return hashes


# --- BSDIFF40 -------------------------------------------------------------------------

def _offtout(x):
	# 64 bit sign-magnitude, little endian
	v = -x if x < 0 else x
	b = bytearray(struct.pack('<Q', v))
	if x < 0:
		b[7] |= 0x80
	return bytes(b)


def bsdiff(old, new):
	"""
	Create a BSDIFF40 patch. The files are text, so the matching is done by lines,
	ignoring whitespace (the retail files have CRLF line endings, base/ has LF).
	Matched lines are copied from the old file except for the bytes that differ,
	all other bytes are stored in the extra block, so only the changes end up in
	the patch.
	"""
	old_lines = old.splitlines(True)
	new_lines = new.splitlines(True)
	old_offs = [0]
	for l in old_lines:
		old_offs.append(old_offs[-1] + len(l))

	def key(line):
		return b' '.join(line.split())

	# ('copy', old offset, length) and ('add', bytes) building the new file
	ops = []
	matcher = difflib.SequenceMatcher(None, [key(l) for l in old_lines], [key(l) for l in new_lines], autojunk=False)
	for tag, i1, i2, j1, j2 in matcher.get_opcodes():
		if tag != 'equal':
			ops.append(('add', b''.join(new_lines[j1:j2])))
			continue
		for i, j in zip(range(i1, i2), range(j1, j2)):
			a, b = old_lines[i], new_lines[j]
			limit = min(len(a), len(b))
			prefix = 0
			while prefix < limit and a[prefix] == b[prefix]:
				prefix += 1
			suffix = 0
			while suffix < limit - prefix and a[-1 - suffix] == b[-1 - suffix]:
				suffix += 1
			ops.append(('copy', old_offs[i], prefix))
			ops.append(('add', b[prefix:len(b) - suffix]))
			ops.append(('copy', old_offs[i] + len(a) - suffix, suffix))

	# control triples: copy x bytes (adding the diff block), add y extra bytes, seek z in the old file
	ctrl = []
	extra = bytearray()
	old_pos = 0	# old file position at the start of the current triple
	x = 0
	y = 0
	for op in ops:
		if op[0] == 'add':
			extra += op[1]
			y += len(op[1])
			continue
		_, offset, length = op
		if not length:
			continue
		if y or offset != old_pos + x:
			ctrl.append((x, y, offset - (old_pos + x)))
			old_pos = offset
			x = y = 0
		x += length
	ctrl.append((x, y, 0))

	# copied bytes are equal, their difference is 0
	diff = bytes(sum(c[0] for c in ctrl))
	ctrl_data = b''.join(_offtout(x) + _offtout(y) + _offtout(z) for x, y, z in ctrl)
	c = bz2.compress(ctrl_data, 9)
	d = bz2.compress(diff, 9)
	e = bz2.compress(bytes(extra), 9)
	return b'BSDIFF40' + _offtout(len(c)) + _offtout(len(d)) + _offtout(len(new)) + c + d + e


def check_patch(old, new, patch):
	"""Apply the patch with the bspatch of the system, it's what the players use."""
	with tempfile.TemporaryDirectory() as tmp:
		paths = [os.path.join(tmp, n) for n in ('old', 'new', 'patch')]
		open(paths[0], 'wb').write(old)
		open(paths[2], 'wb').write(patch)
		subprocess.run(['bspatch', paths[0], paths[1], paths[2]], check=True)
		return open(paths[1], 'rb').read() == new


# --- commands -------------------------------------------------------------------------

def cmd_payload(args):
	entries = read_manifest(args.manifest)
	retail = RetailGame(args.retail)
	if os.path.exists(args.out):
		shutil.rmtree(args.out)
	os.makedirs(args.out)

	lines = ['# pak007.pk4 for Prey2006, generated by release/macos/pak007.py',
		'# copy  <path> <md5>',
		'# patch <path> <md5 of the retail file> <md5 of the result>']
	for kind, path, source in entries:
		src_file = os.path.join(args.repo, source) if source else os.path.join(args.repo, 'base', path)
		data = open(src_file, 'rb').read()
		if kind == 'copy':
			_, retail_data = retail.read(path)
			if retail_data is not None and source is None and retail_data != data:
				print('warning: %s is shipped as it is but also exists in the retail game' % path)
			dst = os.path.join(args.out, 'files', path)
			os.makedirs(os.path.dirname(dst), exist_ok=True)
			open(dst, 'wb').write(data)
			lines.append('copy %s %s' % (path, md5(data)))
		else:
			pak, retail_data = retail.read(path)
			if retail_data is None:
				sys.exit('%s: not in the retail game, it can\'t be patched' % path)
			patch = bsdiff(retail_data, data)
			if not check_patch(retail_data, data, patch):
				sys.exit('%s: the patch doesn\'t reproduce the file' % path)
			dst = os.path.join(args.out, 'patches', path + '.bsdiff')
			os.makedirs(os.path.dirname(dst), exist_ok=True)
			open(dst, 'wb').write(patch)
			lines.append('patch %s %s %s' % (path, md5(retail_data), md5(data)))
		if ' ' in path:
			sys.exit('%s: paths with spaces are not supported' % path)
	open(os.path.join(args.out, 'pak007.list'), 'w').write('\n'.join(lines) + '\n')
	print('pak007 payload: %d files -> %s' % (len(entries), args.out))


def released_paths(manifest):
	return set(path.lower() for _, path, _ in read_manifest(manifest))


def cmd_extras(args):
	released = released_paths(args.manifest)
	base = os.path.join(args.repo, 'base')
	files = []
	for root, _, names in os.walk(base):
		for n in names:
			full = os.path.join(root, n)
			rel = os.path.relpath(full, base).replace(os.sep, '/')
			# default.cfg is an empty placeholder that would replace the key bindings of the game
			if rel.lower() not in released and n != '.DS_Store' and rel != 'default.cfg':
				files.append((full, rel))
	files.sort(key=lambda f: f[1])
	tmp = args.out + '.tmp'
	with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
		for full, rel in files:
			z.write(full, rel)
	os.replace(tmp, args.out)
	for _, rel in files:
		print('  ' + rel)
	print('%d files -> %s' % (len(files), args.out))


def iter_files(directory):
	"""All files in the directory, including the files in zip archives (pk4)."""
	for root, _, names in os.walk(directory):
		for n in names:
			full = os.path.join(root, n)
			if os.path.islink(full):
				continue
			data = open(full, 'rb').read()
			yield os.path.relpath(full, directory), data
			if n.lower().endswith(('.pk4', '.zip')):
				with zipfile.ZipFile(full) as z:
					for info in z.infolist():
						if not info.is_dir():
							yield '%s:%s' % (os.path.relpath(full, directory), info.filename), z.read(info)


def cmd_verify(args):
	retail = RetailGame(args.retail)
	hashes = retail.all_hashes()
	excluded = set()
	if args.manifest:
		released = released_paths(args.manifest)
		base = os.path.join(args.repo, 'base')
		for root, _, names in os.walk(base):
			for n in names:
				full = os.path.join(root, n)
				rel = os.path.relpath(full, base).replace(os.sep, '/')
				if rel.lower() not in released:
					excluded.add(md5(open(full, 'rb').read()))
	problems = 0
	count = 0
	for name, data in iter_files(args.dir):
		count += 1
		h = md5(data)
		if len(data) > 0 and h in hashes:
			print('RETAIL FILE: %s (= %s)' % (name, hashes[h]))
			problems += 1
		elif len(data) > 64 and h in excluded:
			print('NOT RELEASED FILE: %s' % name)
			problems += 1
		elif name.lower().endswith(('.roq', '.pk4')) and ':' not in name:
			print('UNEXPECTED: %s' % name)
			problems += 1
	print('checked %d files, %d problems' % (count, problems))
	return 1 if problems else 0


def main():
	repo = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
	default_retail = os.path.expanduser('~/.local/share/prey06/base')
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument('--repo', default=repo)
	parser.add_argument('--manifest', default=os.path.join(repo, 'release', 'macos', 'pak007.manifest'))
	parser.add_argument('--retail', default=default_retail, help='directory with the retail pk4s')
	sub = parser.add_subparsers(dest='command', required=True)
	p = sub.add_parser('payload')
	p.add_argument('out')
	p = sub.add_parser('extras')
	p.add_argument('out')
	p = sub.add_parser('verify')
	p.add_argument('dir')
	args = parser.parse_args()
	return {'payload': cmd_payload, 'extras': cmd_extras, 'verify': cmd_verify}[args.command](args) or 0


if __name__ == '__main__':
	sys.exit(main())
