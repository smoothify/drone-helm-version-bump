import enum
import os
import io
import click
from ruamel.yaml import YAML
import ast


class ImageTag(enum.Enum):
    NotFound = 0
    Found = 1
    Updated = 2


class PythonLiteralOption(click.Option):

    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)


yaml = YAML(typ='rt')


def urljoin(*args):
    """
    Joins given arguments into an url. Trailing but not leading slashes are
    stripped for each argument.
    """

    return "/".join(map(lambda x: str(x).rstrip('/'), args))


def valid_string(value):
    return isinstance(value, str) and value != ""


def has_image(values: dict) -> bool:
    return "image" in values and valid_string(values['image'])


def has_repository(values: dict) -> bool:
    return "repository" in values and valid_string(values['repository'])


def has_registry(values: dict) -> bool:
    return "registry" in values and valid_string(values['registry'])


def has_tag(values: dict) -> bool:
    return "tag" in values and valid_string(values['tag'])


def image_only(values: dict) -> bool:
    return has_image(values) and \
           not has_tag(values) and \
           not has_registry(values)


def repository_only(values: dict) -> bool:
    return has_repository(values) and \
           not has_tag(values) and \
           not has_registry(values)


def image_tag(values: dict) -> bool:
    return has_image(values) and \
           has_tag(values) and \
           not has_registry(values)


def repository_tag(values: dict) -> bool:
    return has_repository(values) and \
           has_tag(values) and \
           not has_registry(values)


def repository_registry(values: dict) -> bool:
    return has_repository(values) and \
           has_registry(values) and \
           not has_tag(values)


def all_defined(values: dict) -> bool:
    return has_repository(values) and \
           has_tag(values) and \
           has_registry(values)


def process_image(values, images, version) -> ImageTag:
    if image_only(values):
        [image, tag] = values['image'].rsplit(':', 1)
        if image in images:
            if tag.strip() == version:
                return ImageTag.Found

            values['image'] = f'{image}:{version}'
            return ImageTag.Updated

    elif repository_only(values):
        [image, tag] = values['repository'].rsplit(':', 1)
        if image in images:
            if tag.strip() == version:
                return ImageTag.Found

            values['repository'] = f'{image}:{version}'
            return ImageTag.Updated

    elif all_defined(values):
        image = urljoin(values['registry'], values['repository'])
        if image in images:
            if values['tag'].strip() == version:
                return ImageTag.Found

            values['tag'] = version
            return ImageTag.Updated

    elif image_tag(values):
        if values['image'] in images:
            if values['tag'].strip() == version:
                return ImageTag.Found

            values['tag'] = version
            return ImageTag.Updated

    elif repository_tag(values):
        if values['repository'] in images:
            if values['tag'].strip() == version:
                return ImageTag.Found

            values['tag'] = version
            return ImageTag.Updated

    elif repository_registry(values):
        [repository, tag] = values['repository'].rsplit(':', 1)
        image = urljoin(values['registry'], repository)
        if image in images:
            if tag.strip() == version:
                return ImageTag.Found

            values['repository'] = f'{repository}:{version}'
            return ImageTag.Updated

    return ImageTag.NotFound

def process_count(state: ImageTag, found: int, updated: int) -> [int, int]:
    if state == ImageTag.Updated:
        found += 1
        updated += 1
    elif state == ImageTag.Found:
        found +=1

    return found, updated


def find_image_containers(values, images, version, found: int = 0, updated: int = 0) -> [int, int]:

    if "image" in values:
        if isinstance(values['image'], str):
            state = process_image(values, images, version)
            return process_count(state, found, updated)

        elif isinstance(values['image'], dict):
            state = process_image(values['image'], images, version)
            found, updated = process_count(state, found, updated)

    for key, item in values.items():
        if isinstance(item, dict):
            found, updated = find_image_containers(values[key], images, version, found, updated)

    return found, updated


def load_values_file(filename: str):
    with open(filename, 'r') as vf:
        values_text = vf.read()
        values = yaml.load(values_text)
        return values


def save_values_file(filename: str, values):
    with open(filename, 'w') as vf:
        yaml.dump(values, vf)


@click.command()
@click.option('--working-dir', required=True, type=click.Path(file_okay=False, exists=True, resolve_path=True))
@click.option('--values-file', default="values.yaml", type=str)
@click.option('--images', required=True, cls=PythonLiteralOption, default="[]")
@click.option('--version', type=str)
@click.option('--version-file', type=click.File('rb'))
@click.option('--error-no-release', default=False, type=bool)
@click.option('--error-no-tags', default=True, type=bool)
def bump(working_dir: str, values_file: str, images: [str], version: str, version_file: io.BufferedReader,
         error_no_release: bool, error_no_tags: bool):
    if not version and version_file is not None:
        version = version_file.readline().decode().strip()

    if not valid_string(version):
        if error_no_release:
            raise click.MissingParameter(param_type="version")
        else:
            print(f'No version found, skipping...')
    else:
        print(f'Initializing version bump for {version}...')
        print(f'Moving to working directory {working_dir}...')
        os.chdir(working_dir)
        print(f'Loading values from file {values_file}...')
        values_map = load_values_file(values_file)
        print(f'Loaded.')
        print(f'Searching for image tag versions in {values_file}...')
        print(f'Images to search: [{", ".join(images)}]')
        found, updated = find_image_containers(values_map, images, version.strip())

        if updated > 0:
            print(f'{found} image tags found and {updated} updated...')
            print(f'Saving values to file {values_file}...')
            save_values_file(values_file, values_map)
            print(f'Saved.')
        elif found > 0:
            print(f'{found} image tags found and {updated} updated...')
            if error_no_release:
                raise click.BadParameter("no changes in version found")
        else:
            if error_no_tags:
                raise click.BadParameter("no image tags found")
            else:
                print(f'No image tags found, skipping due to error-no-tags option')


if __name__ == '__main__':
    bump(auto_envvar_prefix='PLUGIN')
