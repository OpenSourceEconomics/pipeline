import copy
from pathlib import Path

import jinja2

from pipeline._yaml import read_yaml
from pipeline.exceptions import DuplicatedTaskError


def process_tasks(config):
    user_defined_tasks = _collect_user_defined_tasks(config)
    tasks = _process_user_defined_tasks(user_defined_tasks, config)
    tasks = _replace_task_dependency_with_task_output(tasks)

    return tasks


def replace_missing_templates_with_correct_paths(tasks, missing_templates):
    for id_ in tasks:
        if tasks[id_]["template"] in missing_templates:
            tasks[id_]["template"] = missing_templates[tasks[id_]["template"]]

    return tasks


def _collect_user_defined_tasks(config):
    """Collect the tasks.

    Search recursively through the directories inside the project root and collect
    .yamls

    """
    task_files = list(Path(config["source_directory"]).glob("**/*.yaml"))

    tasks = {}
    for path in task_files:
        try:
            template = jinja2.Template(path.read_text())
        except jinja2.exceptions.TemplateSyntaxError as e:
            message = (
                f"\n\nAn error happened while rendering the task template {path}. "
                "This happens because a jinja2 variable within the template is not "
                "defined, misspelled, etc.."
            )
            raise Exception(message) from e

        rendered_template = template.render(**config)

        tasks_in_file = read_yaml(rendered_template)

        if isinstance(tasks_in_file, dict) and tasks_in_file:
            # Add config location to task_info.
            found_tasks_in_file = {}
            for id_ in tasks_in_file:
                if "template" in tasks_in_file[id_]:
                    found_tasks_in_file[id_] = tasks_in_file[id_]
                    found_tasks_in_file[id_]["config"] = path.as_posix()

            duplicated_ids = set(found_tasks_in_file) & set(tasks)
            if duplicated_ids:
                raise DuplicatedTaskError(duplicated_ids)

            tasks.update(found_tasks_in_file)

    return tasks


def _process_user_defined_tasks(user_defined_tasks, config):
    user_defined_tasks = copy.deepcopy(user_defined_tasks)

    generated_tasks = {}
    for id_, task_info in user_defined_tasks.items():
        if "produces" not in task_info:
            task_info["produces"] = f"{config['hidden_build_directory']}/{id_}"

        generated_tasks.update({id_: task_info})

    return generated_tasks


def _replace_task_dependency_with_task_output(tasks):
    for task_info in tasks.values():
        depends_on = task_info.get("depends_on", [])
        if isinstance(depends_on, list):
            for i, dependency in enumerate(depends_on):
                if dependency in tasks:
                    task_info["depends_on"][i] = tasks[dependency]["produces"]
        else:
            if depends_on in tasks:
                task_info["depends_on"] = tasks[depends_on]["produces"]

    return tasks
