import os
import pytest
from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.exceptions import ResourceViewerIsFake, InternalError

##################
### ResourceViewer
##################

def test_ResourceViewer__with_default_values(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(str(dir_root))

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.is_dir is True
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.content == ''
  assert resource_viewer.children == None

def test_ResourceViewer__with_file(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = 'custom/element.txt'
  is_dir = False
  resource_viewer = ResourceViewer(str(dir_root), element_path, is_dir)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == element_path
  assert resource_viewer.is_dir == is_dir
  assert resource_viewer.name == 'element.txt'
  assert resource_viewer.content == ''
  assert resource_viewer.children == None

def test_ResourceViewer__with_dir(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = 'custom/element'
  is_dir = True
  resource_viewer = ResourceViewer(str(dir_root), element_path, is_dir)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == element_path
  assert resource_viewer.is_dir == is_dir
  assert resource_viewer.name == 'element'
  assert resource_viewer.content == ''
  assert resource_viewer.children == None

def test_ResourceViewer__with_non_normalized_path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = './other_element'
  resource_viewer = ResourceViewer(str(dir_root), element_path)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == 'other_element'
  assert resource_viewer.is_dir is True
  assert resource_viewer.name == 'other_element'
  assert resource_viewer.content == ''
  assert resource_viewer.children == None

##################
### ResourceViewer.build()
##################

def test_ResourceViewer__build__with_directories_and_files(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_root_0 = dir_root / 'dir_root_0'
  dir_root_0.mkdir()
  dir_root_1 = dir_root / 'dir_root_1'
  dir_root_1.mkdir()
  dir_root_1_0 = dir_root_1 / 'dir_root_1_0'
  dir_root_1_0.mkdir()
  FILE_0_CONTENT = 'Content of file 0'
  file_root_0 = dir_root / 'file_root_0.txt'
  file_root_0.write_text(FILE_0_CONTENT)
  FILE_1_CONTENT = 'Content of file 1'
  file_root_1_0_0 = dir_root_1_0 / 'file_root_1_0_0.txt'
  file_root_1_0_0.write_text(FILE_1_CONTENT)
  FILE_2_CONTENT = ''
  file_root_1_0_1 = dir_root_1_0 / 'file_root_1_0_1.txt'
  file_root_1_0_1.write_text(FILE_2_CONTENT)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  assert resource_viewer.children is not None

  for child in resource_viewer.children:
    if child.name == 'dir_root_0':
      dir_root_0_idx = resource_viewer.children.index(child)
    elif child.name == 'dir_root_1':
      dir_root_1_idx = resource_viewer.children.index(child)
    elif child.name == 'file_root_0.txt':
      file_root_0_idx = resource_viewer.children.index(child)

  for child in resource_viewer.children[dir_root_1_idx].children[0].children:
    if child.name == 'file_root_1_0_0.txt':
      file_root_1_0_0_idx = resource_viewer.children[dir_root_1_idx].children[0].children.index(child)
    elif child.name == 'file_root_1_0_1.txt':
      file_root_1_0_1_idx = resource_viewer.children[dir_root_1_idx].children[0].children.index(child)

  # root dir
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.is_dir is True
  assert resource_viewer.content == ''
  assert len(resource_viewer.children) == 3

  # dir with a dir
  assert resource_viewer.children[dir_root_1_idx].name == "dir_root_1"
  assert resource_viewer.children[dir_root_1_idx].element_rel_path == 'dir_root_1'
  assert resource_viewer.children[dir_root_1_idx].is_dir is True
  assert resource_viewer.children[dir_root_1_idx].content == ''
  assert len(resource_viewer.children[dir_root_1_idx].children) == 1

  # dir with files
  assert resource_viewer.children[dir_root_1_idx].children[0].name == "dir_root_1_0"
  assert resource_viewer.children[dir_root_1_idx].children[0].element_rel_path == 'dir_root_1/dir_root_1_0'
  assert resource_viewer.children[dir_root_1_idx].children[0].is_dir is True
  assert resource_viewer.children[dir_root_1_idx].children[0].content == ''
  assert len(resource_viewer.children[dir_root_1_idx].children[0].children) == 2

  # empty file
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].name == "file_root_1_0_1.txt"
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_1.txt'
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].is_dir is False
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].content == FILE_2_CONTENT
  assert len(resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].children) == 0

  # file with content
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].name == "file_root_1_0_0.txt"
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_0.txt'
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].is_dir is False
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].content == FILE_1_CONTENT
  assert len(resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].children) == 0

  # file in root dir
  assert resource_viewer.children[file_root_0_idx].name == "file_root_0.txt"
  assert resource_viewer.children[file_root_0_idx].element_rel_path == 'file_root_0.txt'
  assert resource_viewer.children[file_root_0_idx].is_dir is False
  assert resource_viewer.children[file_root_0_idx].content == FILE_0_CONTENT
  assert len(resource_viewer.children[file_root_0_idx].children) == 0

  # empty dir
  assert resource_viewer.children[dir_root_0_idx].name == "dir_root_0"
  assert resource_viewer.children[dir_root_0_idx].element_rel_path == 'dir_root_0'
  assert resource_viewer.children[dir_root_0_idx].is_dir is True
  assert resource_viewer.children[dir_root_0_idx].content == ''
  assert len(resource_viewer.children[dir_root_0_idx].children) == 0

##################
### ResourceViewer._get_child()
##################

def test_ResourceViewer__get_child__fake(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(os.path.join(dir_root, 'non_existent_element'))
  resource_viewer.build()

  with pytest.raises(ResourceViewerIsFake):
    resource_viewer._get_child('file.txt')

def test_ResourceViewer__get_child__simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  child = resource_viewer._get_child('app')
  assert child is not None
  assert child.name == 'app'

##################
### ResourceViewer.get_element()
##################

def test_ResourceViewer__get_element__fake_(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(os.path.join(dir_root, 'non_existent_element'))
  resource_viewer.build()

  with pytest.raises(ResourceViewerIsFake):
    resource_viewer.get_element('file.txt')

def test_ResourceViewer__get_element__simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  child = resource_viewer.get_element('app')
  assert child is not None
  assert child.name == 'app'

def test_ResourceViewer__get_element__non_existent_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  child = resource_viewer.get_element('app')
  assert child == None

def test_ResourceViewer__get_element__path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()
  dir_app = dir_subdir / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  child = resource_viewer.get_element('subdir/app')
  assert child is not None
  assert child.name == 'app'
  assert child.element_rel_path == 'subdir/app'

def test_ResourceViewer__get_element__non_existent_path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  child = resource_viewer.get_element('subdir/app')
  assert child == None

##################
### ResourceViewer.get_children()
##################

def test_ResourceViewer__get_children__fake(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(os.path.join(dir_root, 'non_existent_element'))
  resource_viewer.build()

  with pytest.raises(ResourceViewerIsFake):
    resource_viewer.get_children()

def test_ResourceViewer__get_children__simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  children = resource_viewer.get_children()
  assert len(children) == 1
  assert children[0].name == 'app'

##################
### ResourceWriter
##################

def test_ResourceWriter__with_default_values(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  assert resource_writer.output_dir_abs_path == str(dir_output)
  assert resource_writer.resources == {}

##################
### ResourceWriter.store_resource()
##################

def test_ResourceWriter__store_resource__multiple(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))
  env_name = 'env'

  resource_writer.store_resource('/a/b/c', 'resource body 1')
  resource_writer.store_resource('/a/b/d', 'resource body 2')
  resource_writer.store_resource('/a/b/e', 'resource body 3')

  assert len(resource_writer.resources) == 3
  assert '/a/b/c' in resource_writer.resources
  assert resource_writer.resources['/a/b/c'] == 'resource body 1'
  assert '/a/b/d' in resource_writer.resources
  assert resource_writer.resources['/a/b/d'] == 'resource body 2'
  assert '/a/b/e' in resource_writer.resources
  assert resource_writer.resources['/a/b/e'] == 'resource body 3'

def test_ResourceWriter__store_resource__duplicate(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))
  env_name = 'env'

  resource_writer.store_resource('/a/b/c', 'resource body 1')
  with pytest.raises(InternalError):
      resource_writer.store_resource('/a/b/c', 'resource body 1')
  assert 'Resource (/a/b/c) already exists' in caplog.text

def test_ResourceWriter__store_resource__undefined_dir_rel_path(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))
  env_name = 'env'

  with pytest.raises(InternalError):
    resource_writer.store_resource(None, 'resource body 1')
  assert 'Parameter `file_path` is undefined' in caplog.text

  with pytest.raises(InternalError):
    resource_writer.store_resource('', 'resource body 1')
  assert 'Parameter `file_path` is undefined' in caplog.text
