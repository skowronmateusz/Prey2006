#!/usr/bin/env python3
"""
Tools for releasing pak007.pk4 without the files of the retail game.

pak007.pk4 (built from base/) holds the port's widescreen HUD, menus and other
fixed assets, but most of these files are modified copies of the retail files
in pak000.pk4. Releases must not contain them, so they ship as binary patches
(BSDIFF40, applied with the bspatch of macOS) against the files of the player's
own copy of the game, see install_assets.sh.

pak007.manifest classifies every file of base/:
	copy    <path> [<source>]  shipped as it is (own work of the port), optionally
	                           taken from <source> (relative to the repo) instead
	patch   <path>             only a patch from the retail file to base/<path> is shipped
	exclude <pattern>          never released (fnmatch pattern, '?' for spaces)

The patches are committed in release/macos/patches, so the release can be built
without the retail game (on CI). Only creating them needs the retail pk4s.

Commands:
	patches  (re)create the patches from the retail pk4s, after changing a patched file
	check    check that the manifest covers base/ and the patches are up to date
	payload  build the payload of the app (files, patches, pak007.list)
	extras   pack the excluded files of base/ into a pk4 (for a local installation)
	verify   check that a directory doesn't contain files of the retail game
"""

import argparse
import bz2
import difflib
import fnmatch
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

RETAIL_PAKS = ['pak000.pk4', 'pak001.pk4', 'pak002.pk4', 'pak003.pk4', 'pak004.pk4']
PATCH_LIST = 'patches.list'

# empty placeholder, it would replace the key bindings of the game (not even in extras)
NEVER_PACKED = {'default.cfg'}


class Error(Exception):
	pass


def md5(data):
	return hashlib.md5(data).hexdigest()


def read_file(path):
	with open(path, 'rb') as f:
		return f.read()


def write_file(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, 'wb') as f:
		f.write(data)


class Manifest:
	def __init__(self, path):
		self.path = path
		self.copies = []	# (path, source or None)
		self.patches = []	# path
		self.excludes = []	# pattern
		with open(path) as f:
			for num, line in enumerate(f, 1):
				line = line.split('#', 1)[0].strip()
				if not line:
					continue
				parts = line.split()
				kind = parts[0]
				if kind == 'copy' and len(parts) in (2, 3):
					self.copies.append((parts[1], parts[2] if len(parts) == 3 else None))
				elif kind == 'patch' and len(parts) == 2:
					self.patches.append(parts[1])
				elif kind == 'exclude' and len(parts) == 2:
					self.excludes.append(parts[1])
				else:
					raise Error('%s:%d: invalid line: %s' % (path, num, line))

	def released(self):
		return set(p.lower() for p, _ in self.copies) | set(p.lower() for p in self.patches)

	def is_excluded(self, path):
		return any(fnmatch.fnmatchcase(path, pattern) for pattern in self.excludes)


def base_files(repo):
	"""Relative paths of all files in base/."""
	base = os.path.join(repo, 'base')
	result = []
	for root, _, names in os.walk(base):
		for n in names:
			if n != '.DS_Store':
				result.append(os.path.relpath(os.path.join(root, n), base).replace(os.sep, '/'))
	return sorted(result)


class RetailGame:
	"""The retail pk4s, searched like the game does (later paks override earlier ones)."""

	def __init__(self, base_dir):
		self.paks = []
		for name in RETAIL_PAKS:
			path = os.path.join(base_dir, name)
			if not os.path.isfile(path):
				raise Error('retail pk4 not found: %s (set --retail)' % path)
			self.paks.append((name, zipfile.ZipFile(path)))
		self.index = {}
		for name, z in self.paks:
			for info in z.infolist():
				if not info.is_dir():
					self.index[info.filename.lower()] = (name, z, info)

	def read(self, path):
		hit = self.index.get(path.lower())
		if not hit:
			return None
		_, z, info = hit
		return z.read(info)

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


def _offtin(b):
	v = struct.unpack('<Q', bytes(b[:7]) + bytes([b[7] & 0x7f]))[0]
	return -v if b[7] & 0x80 else v


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


def patch_extra_size(patch):
	"""Number of bytes stored literally in a patch (the bytes that aren't from the old file)."""
	c, d = _offtin(patch[8:16]), _offtin(patch[16:24])
	return len(bz2.decompress(patch[32 + c + d:]))


def bspatch(old, patch):
	"""Apply a patch with the bspatch of the system, it's what the players use."""
	with tempfile.TemporaryDirectory() as tmp:
		paths = [os.path.join(tmp, n) for n in ('old', 'new', 'patch')]
		write_file(paths[0], old)
		write_file(paths[2], patch)
		subprocess.run(['bspatch', paths[0], paths[1], paths[2]], check=True)
		return read_file(paths[1])


# --- commands -------------------------------------------------------------------------

def read_patch_list(patches_dir):
	"""{path: (md5 of the retail file, md5 of the result)}"""
	result = {}
	list_path = os.path.join(patches_dir, PATCH_LIST)
	if not os.path.isfile(list_path):
		return result
	with open(list_path) as f:
		for line in f:
			if line.startswith('#') or not line.strip():
				continue
			path, src, dst = line.split()
			result[path] = (src, dst)
	return result


def cmd_patches(args):
	manifest = Manifest(args.manifest)
	retail = RetailGame(args.retail)
	if os.path.exists(args.patches):
		shutil.rmtree(args.patches)
	lines = ['# Patches from the retail files to base/, created by "pak007.py patches"',
		'# <path> <md5 of the retail file> <md5 of the result>']
	total = 0
	for path in manifest.patches:
		data = read_file(os.path.join(args.repo, 'base', path))
		retail_data = retail.read(path)
		if retail_data is None:
			raise Error('%s: not in the retail game, it can\'t be patched (use copy?)' % path)
		patch = bsdiff(retail_data, data)
		if bspatch(retail_data, patch) != data:
			raise Error('%s: the patch doesn\'t reproduce the file' % path)
		write_file(os.path.join(args.patches, path + '.bsdiff'), patch)
		lines.append('%s %s %s' % (path, md5(retail_data), md5(data)))
		total += patch_extra_size(patch)
	write_file(os.path.join(args.patches, PATCH_LIST), ('\n'.join(lines) + '\n').encode())
	print('%d patches -> %s (%d bytes of changes)' % (len(manifest.patches), args.patches, total))


def check(repo, manifest, patches_dir):
	"""Problems of the manifest and the patches, as a list of messages."""
	problems = []
	released = manifest.released()
	files = base_files(repo)
	for path in files:
		in_released = path.lower() in released
		excluded = manifest.is_excluded(path)
		if not in_released and not excluded:
			problems.append('%s: not in %s, add it as copy, patch or exclude' % (path, os.path.basename(manifest.path)))
		elif in_released and excluded:
			problems.append('%s: released and excluded at the same time' % path)
	existing = set(f.lower() for f in files)
	for path, source in manifest.copies:
		src = os.path.join(repo, source) if source else os.path.join(repo, 'base', path)
		if not os.path.isfile(src):
			problems.append('%s: %s doesn\'t exist' % (path, src))
		if ' ' in path:
			problems.append('%s: paths with spaces can\'t be released' % path)
	patch_list = read_patch_list(patches_dir)
	for path in manifest.patches:
		if path.lower() not in existing:
			problems.append('%s: not in base/' % path)
			continue
		entry = patch_list.get(path)
		if not entry or not os.path.isfile(os.path.join(patches_dir, path + '.bsdiff')):
			problems.append('%s: no patch, run "pak007.py patches"' % path)
		elif entry[1] != md5(read_file(os.path.join(repo, 'base', path))):
			problems.append('%s: changed since the patch was created, run "pak007.py patches"' % path)
	for path in patch_list:
		if path not in manifest.patches:
			problems.append('%s: patch for a file that isn\'t patched any more, run "pak007.py patches"' % path)
	return problems


def cmd_check(args):
	problems = check(args.repo, Manifest(args.manifest), args.patches)
	for p in problems:
		print(p)
	if problems:
		raise Error('%d problems' % len(problems))
	print('pak007 manifest and patches are up to date')


def cmd_payload(args):
	manifest = Manifest(args.manifest)
	problems = check(args.repo, manifest, args.patches)
	if problems:
		raise Error('\n'.join(problems))
	if os.path.exists(args.out):
		shutil.rmtree(args.out)
	lines = ['# pak007.pk4 for Prey2006, generated by release/macos/pak007.py',
		'# copy  <path> <md5>',
		'# patch <path> <md5 of the retail file> <md5 of the result>']
	for path, source in manifest.copies:
		data = read_file(os.path.join(args.repo, source) if source else os.path.join(args.repo, 'base', path))
		write_file(os.path.join(args.out, 'files', path), data)
		lines.append('copy %s %s' % (path, md5(data)))
	patch_list = read_patch_list(args.patches)
	for path in manifest.patches:
		write_file(os.path.join(args.out, 'patches', path + '.bsdiff'), read_file(os.path.join(args.patches, path + '.bsdiff')))
		src, dst = patch_list[path]
		lines.append('patch %s %s %s' % (path, src, dst))
	write_file(os.path.join(args.out, 'pak007.list'), ('\n'.join(lines) + '\n').encode())
	print('pak007 payload: %d files, %d patches -> %s' % (len(manifest.copies), len(manifest.patches), args.out))


def cmd_extras(args):
	manifest = Manifest(args.manifest)
	files = [f for f in base_files(args.repo) if manifest.is_excluded(f) and f not in NEVER_PACKED]
	tmp = args.out + '.tmp'
	with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
		for rel in files:
			z.write(os.path.join(args.repo, 'base', rel), rel)
	os.replace(tmp, args.out)
	for rel in files:
		print('  ' + rel)
	print('%d files -> %s' % (len(files), args.out))


def iter_files(directory):
	"""All files in the directory, including the files in zip archives (pk4)."""
	for root, _, names in os.walk(directory):
		for n in names:
			full = os.path.join(root, n)
			if os.path.islink(full):
				continue
			yield os.path.relpath(full, directory), read_file(full)
			if n.lower().endswith(('.pk4', '.zip')):
				with zipfile.ZipFile(full) as z:
					for info in z.infolist():
						if not info.is_dir():
							yield '%s:%s' % (os.path.relpath(full, directory), info.filename), z.read(info)


def cmd_verify(args):
	retail_hashes = {}
	if os.path.isfile(os.path.join(args.retail, RETAIL_PAKS[0])):
		retail_hashes = RetailGame(args.retail).all_hashes()
	else:
		print('warning: retail game not found in %s, only checking against the excluded files of base/' % args.retail)
	manifest = Manifest(args.manifest)
	excluded = {}
	for path in base_files(args.repo):
		if path.lower() not in manifest.released():
			data = read_file(os.path.join(args.repo, 'base', path))
			if len(data) > 64:	# small files like an empty default.cfg can be equal to anything
				excluded[md5(data)] = path
	problems = 0
	count = 0
	for name, data in iter_files(args.dir):
		count += 1
		h = md5(data)
		if data and h in retail_hashes:
			print('RETAIL FILE: %s (= %s)' % (name, retail_hashes[h]))
			problems += 1
		elif h in excluded:
			print('NOT RELEASED FILE: %s (= base/%s)' % (name, excluded[h]))
			problems += 1
		elif name.lower().endswith(('.roq', '.pk4')) and ':' not in name:
			print('UNEXPECTED: %s' % name)
			problems += 1
	print('checked %d files, %d problems' % (count, problems))
	if problems:
		raise Error('files that must not be released were found')


def main(argv=None):
	repo = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument('--repo', default=repo)
	parser.add_argument('--manifest', help='default: <repo>/release/macos/pak007.manifest')
	parser.add_argument('--patches', help='default: <repo>/release/macos/patches')
	parser.add_argument('--retail', default=os.environ.get('PREY_RETAIL_DIR', os.path.expanduser('~/.local/share/prey06/base')),
		help='directory with the retail pk4s (default: $PREY_RETAIL_DIR or ~/.local/share/prey06/base)')
	sub = parser.add_subparsers(dest='command', required=True)
	sub.add_parser('patches')
	sub.add_parser('check')
	sub.add_parser('payload').add_argument('out')
	sub.add_parser('extras').add_argument('out')
	sub.add_parser('verify').add_argument('dir')
	args = parser.parse_args(argv)
	args.manifest = args.manifest or os.path.join(args.repo, 'release', 'macos', 'pak007.manifest')
	args.patches = args.patches or os.path.join(args.repo, 'release', 'macos', 'patches')
	commands = {'patches': cmd_patches, 'check': cmd_check, 'payload': cmd_payload, 'extras': cmd_extras, 'verify': cmd_verify}
	try:
		commands[args.command](args)
	except Error as e:
		print('error: %s' % e, file=sys.stderr)
		return 1
	return 0


if __name__ == '__main__':
	sys.exit(main())
