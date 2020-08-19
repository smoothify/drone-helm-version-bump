import enum
import os
import io
from typing import List

import click
from ruamel.yaml import YAML


class ImageTag(enum.Enum):
    NotFound = 0
    Found = 1
    Updated = 2


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


def load_yaml_file(filename: str):
    with open(filename, 'r') as vf:
        values_text = vf.read()
        values = yaml.load(values_text)
        return values


def save_yaml_file(filename: str, values):
    with open(filename, 'w') as vf:
        yaml.dump(values, vf)


@click.command()
@click.option('--working-dir', required=True, type=click.Path(file_okay=False, exists=True, resolve_path=True))
@click.option('--chart-file', default="Chart.yaml", type=str)
@click.option('--chart-version', type=str)
@click.option('--chart-version-file', type=click.File('rb'))
@click.option('--skip-chart-version', default=False, type=bool)
@click.option('--app-version', type=str)
@click.option('--app-version-file', type=click.File('rb'))
@click.option('--skip-app-version', default=False, type=bool)
@click.option('--values-file', default="values.yaml", type=str)
@click.option('--image', type=str)
@click.option('--image-version', '--version', type=str)
@click.option('--image-version-file', '--version-file', type=click.File('rb'))
@click.option('--error-no-chart-version', default=False, type=bool)
@click.option('--error-no-app-version', default=False, type=bool)
@click.option('--error-no-image-version', default=False, type=bool)
@click.option('--error-no-release', default=False, type=bool)
@click.option('--error-no-tags', default=True, type=bool)
def bump(working_dir: str, chart_file: str, chart_version: str, chart_version_file: io.BufferedReader,
         skip_chart_version: bool, app_version: str, app_version_file: io.BufferedReader, skip_app_version: bool,
         values_file: str, image: str, image_version: str, image_version_file: io.BufferedReader,
         error_no_chart_version: bool, error_no_app_version: bool, error_no_image_version: bool,
         error_no_release: bool, error_no_tags: bool):

    if not skip_chart_version:
        if not chart_version and chart_version_file is not None:
            chart_version = chart_version_file.readline().decode().strip()
        if not valid_string(chart_version):
            if error_no_chart_version:
                raise click.MissingParameter(param_type="chart-version")
            else:
                print(f'no chart version found, skipping...')

    if not skip_app_version:
        if not app_version and app_version_file is not None:
            app_version = app_version_file.readline().decode().strip()
        if not valid_string(app_version):
            if error_no_app_version:
                raise click.MissingParameter(param_type="app-version")
            else:
                print(f'no app version found, skipping...')

    images = List[str]
    if image is not None:
        images = image.lstrip("[").rstrip("]").replace('"','').replace("'",'').split(",")

        if len(images) == 0:
            raise click.BadParameter("No valid images specified")

        if not image_version and image_version_file is not None:
            image_version = image_version_file.readline().decode().strip()

        if not valid_string(image_version):
            if error_no_image_version:
                raise click.MissingParameter(param_type="image-version")
            else:
                print(f'image provided, but no image version found, skipping...')

    print(f'Initializing version bump...')
    print(f'Moving to working directory {working_dir}...')
    os.chdir(working_dir)

    release_found = False

    if chart_version or app_version:
        changed = False
        print(f'Loading file {chart_file}...')
        chart_map = load_yaml_file(chart_file)
        print(f'Loaded.')
        if chart_version:
            if chart_version != chart_map.get("version", None):
                print(f'Updating chart version to {chart_version}...')
                chart_map["version"] = chart_version
                changed = True
            else:
                print(f'No changes to chart version ({chart_version}) skipping...')

        if app_version:
            if app_version != chart_map.get("appVersion", None):
                print(f'Updating app version to {app_version}...')
                chart_map["appVersion"] = app_version
                changed = True
            else:
                print(f'No changes to app version ({app_version}) skipping...')

        if changed:
            print(f'Saving file {chart_file}...')
            save_yaml_file(chart_file, chart_map)
            release_found = True

    if image:
        print(f'Loading values from file {values_file}...')
        values_map = load_yaml_file(values_file)
        print(f'Loaded.')
        print(f'Searching for image tag versions in {values_file}...')
        print(f'Images to search: [{", ".join(images)}]')
        found, updated = find_image_containers(values_map, images, image_version.strip())

        if updated > 0:
            release_found = True
            print(f'{found} image tags found and {updated} updated...')
            print(f'Saving values to file {values_file}...')
            save_yaml_file(values_file, values_map)
            print(f'Saved.')
        elif found > 0:
            print(f'{found} image tags found and {updated} updated...')
        else:
            if error_no_tags:
                raise click.BadParameter("no image tags found")
            else:
                print(f'No image tags found, skipping due to error-no-tags option')

    if error_no_release and not release_found:
        raise click.BadParameter("no changes found in chart, app or image versions")


if __name__ == '__main__':
    bump(auto_envvar_prefix='PLUGIN')
