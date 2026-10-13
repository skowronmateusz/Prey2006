"""
Tests of the macOS release tools, without the retail game: a fake game and repo are
created in a temporary directory.

	python3 -m unittest discover -s release/macos/tests -v
"""

import os
import random
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
MACOS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(MACOS))
sys.path.insert(0, MACOS)

import pak007  # noqa: E402


def write(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, 'wb') as f:
		f.write(data)


def crlf(text):
	return text.replace(b'\n', b'\r\n')


def gui_text(seed, lines=300):
	rnd = random.Random(seed)
	words = [b'windowDef', b'rect', b'visible', b'backcolor', b'onTime', b'set', b'"desktop::x"', b'0,', b'640,', b'480', b'{', b'}']
	return b''.join(b'\t' * rnd.randint(0, 3) + b' '.join(rnd.choice(words) for _ in range(rnd.randint(1, 8))) + b'\n'
		for _ in range(lines))


class BsdiffTest(unittest.TestCase):
	def roundtrip(self, old, new):
		patch = pak007.bsdiff(old, new)
		self.assertEqual(pak007.bspatch(old, patch), new)
		return patch

	def test_edge_cases(self):
		self.roundtrip(b'', b'')
		self.roundtrip(b'', b'new file\n')
		self.roundtrip(b'old file\n', b'')
		self.roundtrip(b'no newline at the end', b'no newline at the end, changed')
		self.roundtrip(b'a\nb\nc\n', b'c\nb\na\n')
		self.roundtrip(bytes(range(256)) * 10, bytes(reversed(range(256))) * 10)

	def test_random_edits(self):
		rnd = random.Random(1)
		for seed in range(20):
			old = gui_text(seed).split(b'\n')
			new = list(old)
			for _ in range(rnd.randint(1, 30)):
				pos = rnd.randrange(len(new))
				op = rnd.choice(['insert', 'delete', 'change', 'indent'])
				if op == 'insert':
					new.insert(pos, b'\tanchor\tANCHOR_CENTER_CENTER')
				elif op == 'delete':
					del new[pos]
				elif op == 'change':
					new[pos] = new[pos] + b' // changed'
				else:
					new[pos] = b'    ' + new[pos].lstrip()
			self.roundtrip(crlf(b'\n'.join(old)), b'\n'.join(new))

	def test_only_changes_in_patch(self):
		# retail files are CRLF, base/ is LF: the patch must not contain the unchanged lines
		new = gui_text(42, 2000)
		old = crlf(new.replace(b'visible', b'visible', 1))
		new = new.replace(b'backcolor', b'forecolor', 1)
		patch = self.roundtrip(old, new)
		self.assertLess(pak007.patch_extra_size(patch), len(new) // 100)


class FakeProject:
	"""A repo with base/ and a manifest, and a retail game in the same temporary directory."""

	def __init__(self, tmp):
		self.repo = os.path.join(tmp, 'repo')
		self.retail = os.path.join(tmp, 'retail')
		self.data = os.path.join(tmp, 'data')
		self.manifest = os.path.join(self.repo, 'release', 'macos', 'pak007.manifest')
		self.patches = os.path.join(self.repo, 'release', 'macos', 'patches')
		self.retail_files = {
			'guis/hud.gui': crlf(gui_text(1)),
			'guis/mainmenu/mainmenu_options.guifragment': crlf(gui_text(2)),
			'materials/gfx.mtr': crlf(b'textures/region\n{\n\tforceopaque\n}\n'),
			'guis/assets/loading/loading.tga': b'\x00\x00\x02' + bytes(range(256)) * 40,
			'default.cfg': crlf(b'bind w _forward\n'),
		}
		self.base_files = {
			'guis/hud.gui': gui_text(1).replace(b'rect', b'anchor ANCHOR_CENTER_CENTER\n\trect', 3),
			'guis/mainmenu/mainmenu_options.guifragment': gui_text(2) + b'windowDef new { }\n',
			# override the retail one by an older patch level (pak003 wins over pak000)
			'materials/gfx.mtr': b'textures/region\n{\n\tforceopaque\n}\ntextures/black\n{\n\tmap _black\n}\n',
			'guis/anchors.guifragment': b'#define ANCHOR_CENTER_CENTER 4\n',
			'guis/assets/loading/loading.tga': b'\x00\x00\x02' + bytes(reversed(range(256))) * 40,
			'video/intro.roq': b'RoQ' + bytes(1000),
			'maps/Tutorial Maps/test.map': b'Version 2\n' * 20,
			'default.cfg': b'# empty file\n',
		}
		for path, data in self.base_files.items():
			write(os.path.join(self.repo, 'base', path), data)
		write(os.path.join(self.repo, 'release', 'macos', 'assets', 'console.tga'), b'own console texture')
		self.write_manifest()
		# retail paks: everything in pak000, an older version of gfx.mtr in pak000 and the newest in pak003
		paks = {name: {} for name in pak007.RETAIL_PAKS}
		paks['pak000.pk4'] = dict(self.retail_files)
		paks['pak000.pk4']['materials/gfx.mtr'] = crlf(b'// old version\n')
		paks['pak003.pk4']['materials/gfx.mtr'] = self.retail_files['materials/gfx.mtr']
		paks['pak001.pk4']['textures/other.tga'] = b'other retail file' * 10
		os.makedirs(self.retail)
		for name, files in paks.items():
			with zipfile.ZipFile(os.path.join(self.retail, name), 'w', zipfile.ZIP_DEFLATED) as z:
				for path, data in files.items():
					z.writestr(path, data)

	def write_manifest(self, extra=''):
		write(self.manifest, ('''
copy  guis/anchors.guifragment
copy  textures/gfx/console.tga  release/macos/assets/console.tga
patch guis/hud.gui
patch guis/mainmenu/mainmenu_options.guifragment
patch materials/gfx.mtr
exclude default.cfg
exclude guis/assets/loading/*
exclude video/*.roq
exclude maps/Tutorial?Maps/*
''' + extra).encode())

	def tool(self, *args, retail=True):
		cmd = [sys.executable, '-I', os.path.join(MACOS, 'pak007.py'), '--repo', self.repo,
			'--manifest', self.manifest, '--patches', self.patches]
		if retail:
			cmd += ['--retail', self.retail]
		else:
			cmd += ['--retail', os.path.join(self.repo, 'no-retail-here')]
		return subprocess.run(cmd + list(args), capture_output=True, text=True)

	def install(self, *args):
		return subprocess.run(['bash', os.path.join(self.payload_dir, '..', 'install_assets.sh')] + list(args),
			capture_output=True, text=True)

	def build_payload(self):
		"""Payload and installer like in the app: Resources/install_assets.sh and Resources/pak007."""
		resources = os.path.join(os.path.dirname(self.repo), 'Resources')
		self.payload_dir = os.path.join(resources, 'pak007')
		r = self.tool('payload', self.payload_dir, retail=False)
		if r.returncode != 0:
			raise AssertionError(r.stdout + r.stderr)
		with open(os.path.join(MACOS, 'install_assets.sh'), 'rb') as f:
			write(os.path.join(resources, 'install_assets.sh'), f.read())

	def copy_retail_to_data(self):
		os.makedirs(self.data, exist_ok=True)
		for name in pak007.RETAIL_PAKS:
			os.symlink(os.path.join(self.retail, name), os.path.join(self.data, name))


class ReleaseToolsTest(unittest.TestCase):
	def setUp(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		self.p = FakeProject(self.tmpdir.name)

	def tearDown(self):
		self.tmpdir.cleanup()

	def assertOk(self, result):
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

	def test_check_needs_patches(self):
		r = self.p.tool('check', retail=False)
		self.assertNotEqual(r.returncode, 0)
		self.assertIn('no patch', r.stdout)
		self.assertOk(self.p.tool('patches'))
		self.assertOk(self.p.tool('check', retail=False))

	def test_check_finds_changed_file(self):
		self.assertOk(self.p.tool('patches'))
		write(os.path.join(self.p.repo, 'base', 'guis', 'hud.gui'), b'changed\n')
		r = self.p.tool('check', retail=False)
		self.assertNotEqual(r.returncode, 0)
		self.assertIn('guis/hud.gui: changed since the patch was created', r.stdout)
		self.assertNotEqual(self.p.tool('payload', os.path.join(self.tmpdir.name, 'out'), retail=False).returncode, 0)

	def test_check_finds_unlisted_file(self):
		self.assertOk(self.p.tool('patches'))
		write(os.path.join(self.p.repo, 'base', 'guis', 'new.gui'), b'new\n')
		r = self.p.tool('check', retail=False)
		self.assertNotEqual(r.returncode, 0)
		self.assertIn('guis/new.gui: not in pak007.manifest', r.stdout)

	def test_check_finds_released_and_excluded(self):
		self.p.write_manifest('exclude guis/hud.gui\n')
		self.assertOk(self.p.tool('patches'))
		r = self.p.tool('check', retail=False)
		self.assertIn('guis/hud.gui: released and excluded', r.stdout)

	def test_patch_needs_retail_file(self):
		self.p.write_manifest('patch guis/anchors.guifragment\n')
		r = self.p.tool('patches')
		self.assertNotEqual(r.returncode, 0)
		self.assertIn('not in the retail game', r.stderr)

	def test_install(self):
		self.assertOk(self.p.tool('patches'))
		self.p.build_payload()

		os.makedirs(self.p.data)
		self.assertEqual(self.p.install('--check', self.p.data).returncode, 2)	# no game data
		self.assertEqual(self.p.install(self.p.data).returncode, 2)

		self.p.copy_retail_to_data()
		self.assertEqual(self.p.install('--check', self.p.data).returncode, 1)	# pak007.pk4 missing
		self.assertOk(self.p.install(self.p.data))
		self.assertEqual(self.p.install('--check', self.p.data).returncode, 0)

		with zipfile.ZipFile(os.path.join(self.p.data, 'pak007.pk4')) as z:
			files = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
		expected = {path: self.p.base_files[path] for path in
			('guis/hud.gui', 'guis/mainmenu/mainmenu_options.guifragment', 'materials/gfx.mtr', 'guis/anchors.guifragment')}
		expected['textures/gfx/console.tga'] = b'own console texture'
		self.assertEqual(files, expected)

		# a new version of the app (different payload) rebuilds pak007.pk4
		with open(os.path.join(self.p.payload_dir, 'pak007.list'), 'a') as f:
			f.write('# new version\n')
		self.assertEqual(self.p.install('--check', self.p.data).returncode, 1)

	def test_install_other_game_version(self):
		self.assertOk(self.p.tool('patches'))
		self.p.build_payload()
		# a game with another version of hud.gui
		os.makedirs(self.p.data)
		for name in pak007.RETAIL_PAKS:
			with zipfile.ZipFile(os.path.join(self.p.retail, name)) as src, \
				zipfile.ZipFile(os.path.join(self.p.data, name), 'w') as dst:
				for info in src.infolist():
					data = src.read(info)
					if info.filename == 'guis/hud.gui':
						data = b'// patched by someone else\r\n' + data
					dst.writestr(info, data)
		r = self.p.install(self.p.data)
		self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
		self.assertIn('guis/hud.gui', r.stderr)
		with zipfile.ZipFile(os.path.join(self.p.data, 'pak007.pk4')) as z:
			names = z.namelist()
		self.assertNotIn('guis/hud.gui', names)
		self.assertIn('guis/mainmenu/mainmenu_options.guifragment', names)

	def test_verify(self):
		self.assertOk(self.p.tool('patches'))
		self.p.build_payload()
		app = os.path.dirname(self.p.payload_dir)
		self.assertOk(self.p.tool('verify', app))
		self.assertOk(self.p.tool('verify', app, retail=False))

		# a retail file, also inside a pk4
		with zipfile.ZipFile(os.path.join(app, 'data.zip'), 'w') as z:
			z.writestr('materials/old.mtr', self.p.retail_files['guis/hud.gui'])
		r = self.p.tool('verify', app)
		self.assertNotEqual(r.returncode, 0)
		self.assertIn('RETAIL FILE: data.zip:materials/old.mtr', r.stdout)
		os.remove(os.path.join(app, 'data.zip'))

		# an excluded file of base/ (found without the retail game)
		write(os.path.join(app, 'loading.tga'), self.p.base_files['guis/assets/loading/loading.tga'])
		r = self.p.tool('verify', app, retail=False)
		self.assertNotEqual(r.returncode, 0)
		self.assertIn('NOT RELEASED FILE: loading.tga', r.stdout)

	def test_extras(self):
		out = os.path.join(self.tmpdir.name, 'extras.pk4')
		self.assertOk(self.p.tool('extras', out, retail=False))
		with zipfile.ZipFile(out) as z:
			self.assertEqual(sorted(z.namelist()),
				['guis/assets/loading/loading.tga', 'maps/Tutorial Maps/test.map', 'video/intro.roq'])


class RepositoryTest(unittest.TestCase):
	"""The manifest and the committed patches of this repository."""

	def test_manifest_and_patches_up_to_date(self):
		manifest = pak007.Manifest(os.path.join(MACOS, 'pak007.manifest'))
		problems = pak007.check(REPO, manifest, os.path.join(MACOS, 'patches'))
		self.assertEqual(problems, [])

	def test_patches_contain_only_changes(self):
		# a patch with (almost) the whole file means the line endings weren't ignored
		patches = os.path.join(MACOS, 'patches')
		for path, (_, dst) in pak007.read_patch_list(patches).items():
			with open(os.path.join(patches, path + '.bsdiff'), 'rb') as f:
				extra = pak007.patch_extra_size(f.read())
			size = os.path.getsize(os.path.join(REPO, 'base', path))
			self.assertLess(extra, max(size * 0.5, 1024), path)

	def test_scripts_syntax(self):
		for script in ('build_release.sh', 'install_assets.sh', 'launcher.sh'):
			r = subprocess.run(['bash', '-n', os.path.join(MACOS, script)], capture_output=True, text=True)
			self.assertEqual(r.returncode, 0, script + ': ' + r.stderr)


if __name__ == '__main__':
	unittest.main()
