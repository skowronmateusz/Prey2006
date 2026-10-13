"""
Tests of a built Prey2006.app (run by build_release.sh):

	PREY2006_APP=build-release/macos/Prey2006.app python3 -m unittest discover -s release/macos/tests -p 'test_app.py' -v
"""

import os
import plistlib
import subprocess
import tempfile
import unittest

APP = os.environ.get('PREY2006_APP')
CONTENTS = os.path.join(APP, 'Contents') if APP else None


def run(*cmd, **kwargs):
	return subprocess.run(list(cmd), capture_output=True, text=True, **kwargs)


def macho_files():
	result = []
	for root, _, names in os.walk(CONTENTS):
		for n in names:
			path = os.path.join(root, n)
			if not os.path.islink(path) and run('file', '-b', path).stdout.startswith('Mach-O'):
				result.append(path)
	return result


@unittest.skipUnless(APP, 'set PREY2006_APP to the app bundle')
class AppTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(os.path.join(CONTENTS, 'Info.plist'), 'rb') as f:
			cls.info = plistlib.load(f)

	def test_info_plist(self):
		self.assertEqual(run('plutil', '-lint', os.path.join(CONTENTS, 'Info.plist')).returncode, 0)
		executable = os.path.join(CONTENTS, 'MacOS', self.info['CFBundleExecutable'])
		self.assertTrue(os.access(executable, os.X_OK), executable)
		self.assertTrue(os.path.isfile(os.path.join(CONTENTS, 'Resources', self.info['CFBundleIconFile'] + '.icns')))

	def test_signature(self):
		r = run('codesign', '--verify', '--deep', '--strict', APP)
		self.assertEqual(r.returncode, 0, r.stderr)

	def test_binaries(self):
		files = macho_files()
		names = set(os.path.basename(f) for f in files)
		self.assertTrue({'prey06', 'prey06ded', 'gamearm64.dylib', 'libSDL2-2.0.0.dylib', 'libopenal.1.dylib'} <= names, names)
		frameworks = set(os.listdir(os.path.join(CONTENTS, 'Frameworks')))
		for path in files:
			name = os.path.basename(path)
			self.assertEqual(run('lipo', '-archs', path).stdout.split(), ['arm64'], name)
			load = run('otool', '-l', path).stdout
			minos = load.split('minos', 1)[1].split()[0]
			self.assertEqual(minos, self.info['LSMinimumSystemVersion'], name + ' needs a newer macOS')
			# only the app bundle, no build directories
			rpaths = [l.split()[1] for l in load.splitlines() if l.strip().startswith('path ')]
			for rp in rpaths:
				self.assertEqual(rp, '@executable_path/../Frameworks', name)
			for line in run('otool', '-L', path).stdout.splitlines()[1:]:
				dep = line.split()[0]
				if dep.startswith('@rpath/'):
					lib = dep[len('@rpath/'):]
					self.assertTrue(lib in frameworks or lib == name, '%s: %s not in Frameworks' % (name, lib))
				else:
					self.assertRegex(dep, r'^(/usr/lib/|/System/)', name)

	def test_engine_starts(self):
		# without game data the engine stops when it can't find default.cfg: this shows that
		# the libraries are loaded and the engine initializes
		with tempfile.TemporaryDirectory() as home:
			env = dict(os.environ, HOME=home)
			r = run(os.path.join(CONTENTS, 'MacOS', 'prey06ded'), env=env, timeout=120)
		self.assertIn("Couldn't load default.cfg", r.stdout + r.stderr)

	def test_payload(self):
		resources = os.path.join(CONTENTS, 'Resources')
		patched = 0
		with open(os.path.join(resources, 'pak007', 'pak007.list')) as f:
			for line in f:
				if line.startswith('#'):
					continue
				kind, path = line.split()[:2]
				sub = 'files/' + path if kind == 'copy' else 'patches/' + path + '.bsdiff'
				self.assertTrue(os.path.isfile(os.path.join(resources, 'pak007', sub)), sub)
				patched += kind == 'patch'
		self.assertGreater(patched, 0)
		with tempfile.TemporaryDirectory() as data:
			r = run(os.path.join(resources, 'install_assets.sh'), '--check', data)
		self.assertEqual(r.returncode, 2)

	def test_licenses(self):
		licenses = os.listdir(os.path.join(CONTENTS, 'Resources', 'licenses'))
		for name in ('GPL', 'SDL2', 'OpenAL'):
			self.assertTrue(any(name in l for l in licenses), name)


if __name__ == '__main__':
	unittest.main()
