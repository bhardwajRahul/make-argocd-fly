import logging
import os
import re
import socket
import jinja2
from typing import Tuple, Callable, Union, List
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader, FunctionLoader, nodes, StrictUndefined
from jinja2.ext import Extension
from markupsafe import Markup

from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.exceptions import UndefinedTemplateVariableError, MissingFileError, InternalError
from make_argocd_fly.utils import extract_undefined_variable

log = logging.getLogger(__name__)


class AbstractRenderer(ABC):
  @abstractmethod
  def render(self, content: str) -> str:
    pass


class YamlRenderer(AbstractRenderer):
  def __init__(self) -> None:
    pass

  def render(self, content: str | None) -> str | None:
    return content


class DigExtension(Extension):
  def __init__(self, environment):
    super(DigExtension, self).__init__(environment)
    self.environment.filters['dig'] = self.dig_filter

  def dig_filter(self, host):
    try:
      ip_address = socket.gethostbyname(host)
      return ip_address
    except socket.gaierror:
      return None


class CustomFunctionLoader(FunctionLoader):
  def __init__(
        self,
        load_func: Callable[[str], Union[str, Tuple[str, str | None, Callable[[], bool] | None]]],
        render_func: Callable[[str], Union[str, Tuple[str, str | None, Callable[[], bool] | None]]],
        list_func: Callable[[str], List[ResourceViewer]],
  ) -> None:
    super().__init__(load_func)
    self.render_func = render_func
    self.list_func = list_func

  def get_rendered(self, environment: 'Environment', template: str) -> Tuple[str, str | None, Callable[[], bool] | None]:
    rv = self.render_func(template)

    if rv is None:
      raise MissingFileError(template)

    if isinstance(rv, str):
      return rv, None, None

    return rv

  def list_templates(self, path: str) -> List[ResourceViewer]:
    return self.list_func(path)


class IncludeRawExtension(Extension):
  tags = {'include_raw'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:include_raw').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, filename):
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError

    loaded_template = self.environment.loader.get_source(self.environment, filename)
    content = loaded_template[0] if loaded_template else ''

    return Markup(content)


# This extension is used to output the name of the file as a yaml list
class IncludeAllAsYamlNamesListExtension(Extension):
  tags = {'include_all_as_yaml_names_list'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:include_all_as_yaml_names_list').lineno
    template = parser.parse_expression()
    base_path = parser.parse_expression() if parser.stream.skip_if('comma') else None
    result = self.call_method('_render', [template, base_path], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str, base_path: str | None = None) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError

    base_path = base_path or ''
    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    yaml_names_as_list = []

    for child in children:
      if child.name.endswith('.j2'):
        loaded_template = self.environment.loader.get_rendered(self.environment, child.element_rel_path)
        child_name = child.name[:-3]
      else:
        loaded_template = self.environment.loader.get_source(self.environment, child.element_rel_path)
        child_name = child.name

      if loaded_template:
        child_content = loaded_template[0]
        # if child_content is empty, skip adding it to the yaml
        if child_content == '':
          log.debug('No content in ' + child_name + ', not adding to yaml')
          continue

      yaml_names_as_list.append(f'- {base_path}{child_name}\n')

    return Markup(''.join(yaml_names_as_list))


class IncludeAllAsYamlKVExtension(Extension):
  tags = {'include_all_as_yaml_kv'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:include_all_as_yaml_kv').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError

    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      if child.name.endswith('.j2'):
        loaded_template = self.environment.loader.get_rendered(self.environment, child.element_rel_path)
        child_name = child.name[:-3]
      else:
        loaded_template = self.environment.loader.get_source(self.environment, child.element_rel_path)
        child_name = child.name

      if loaded_template:
        child_content = loaded_template[0]
        # if child_content is empty, skip adding it to the yaml
        if child_content == '':
          log.debug('No content in ' + child_name + ', not adding to yaml')
          continue

        kv_as_yaml_str.append('{}: |\n  {}\n'.format(child_name, re.sub('\n', '\n  ', child_content.strip())))

    return Markup(''.join(kv_as_yaml_str))


class IncludeAllAsYamlListExtension(Extension):
  tags = {'include_all_as_yaml_list'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:include_all_as_yaml_list').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError

    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      if child.name.endswith('.j2'):
        loaded_template = self.environment.loader.get_rendered(self.environment, child.element_rel_path)
      else:
        loaded_template = self.environment.loader.get_source(self.environment, child.element_rel_path)

      if loaded_template:
        child_content = loaded_template[0]
        # if child_content is empty, skip adding it to the yaml
        if child_content == '':
          continue
      kv_as_yaml_str.append('- {}\n'.format(re.sub('\n', '\n  ', child_content.strip())))

    return Markup(''.join(kv_as_yaml_str))


class JinjaRendererFromViewer(AbstractRenderer):
  def __init__(self, viewer: ResourceViewer) -> None:
    self.viewer = viewer
    self.loader = CustomFunctionLoader(self._get_source, self._get_rendered, self._list_templates)
    self.env = Environment(extensions=[IncludeRawExtension,
                                       IncludeAllAsYamlNamesListExtension,
                                       IncludeAllAsYamlKVExtension,
                                       IncludeAllAsYamlListExtension,
                                       DigExtension,
                                       'jinja2_ansible_filters.AnsibleCoreFiltersExtension'],
                           loader=self.loader,
                           undefined=StrictUndefined)

    self.template_vars = {}
    self.filename = '<template>'

  def _get_source(self, path: str):
    files_children = self.viewer.get_files_children(os.path.basename(path))
    for file_child in files_children:
      if file_child.element_rel_path == path:
        return (file_child.content, path, None)

    log.error(f'Missing file {path}')
    raise MissingFileError(path)

  def _get_rendered(self, path: str):
    files_children = self.viewer.get_files_children(os.path.basename(path))
    for file_child in files_children:
      if file_child.element_rel_path == path:
        return (self.render(file_child.content), path, None)

    log.error(f'Missing file {path}')
    raise MissingFileError(path)

  def _list_templates(self, path: str) -> List[ResourceViewer]:
    element = self.viewer.get_element(path)
    if not element or not element.is_dir:
      log.error(f'Provided path {path} is not a directory')
      return []

    return element.get_files_children('.+')

  def set_template_vars(self, template_vars: dict) -> None:
    self.template_vars = template_vars

  def set_filename(self, filename: str) -> None:
    self.filename = filename

  def render(self, content: str) -> str:
    template = self.env.from_string(content)
    template.filename = self.filename

    try:
      rendered = template.render(self.template_vars)
    except jinja2.exceptions.UndefinedError as e:
      variable_name = extract_undefined_variable(str(e))

      log.error(f'Variable "{variable_name}" is undefined')
      raise UndefinedTemplateVariableError(variable_name) from None

    return rendered


class JinjaRenderer(AbstractRenderer):
  def __init__(self) -> None:
    self.loader = BaseLoader()
    self.env = Environment(extensions=[DigExtension,
                                       'jinja2_ansible_filters.AnsibleCoreFiltersExtension'],
                           loader=self.loader,
                           undefined=StrictUndefined)

    self.template_vars = {}

  def set_template_vars(self, template_vars: dict) -> None:
    self.template_vars = template_vars

  def render(self, content: str) -> str:
    template = self.env.from_string(content)

    try:
      rendered = template.render(self.template_vars)
    except jinja2.exceptions.UndefinedError as e:
      variable_name = extract_undefined_variable(str(e))

      log.error(f'Variable "{variable_name}" is undefined')
      raise UndefinedTemplateVariableError(variable_name) from None

    return rendered
