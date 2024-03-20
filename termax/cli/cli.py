import os
import click
import inquirer
import subprocess
from rich.console import Console

import termax
from termax.utils.const import *
from termax.prompt import Prompt, Memory
from termax.utils import Config, CONFIG_PATH
from termax.agent import OpenAIModel, GeminiModel, ClaudeModel, QianFanModel, MistralModel, QianWenModel


class DefaultCommandGroup(click.Group):
    """allow a default command for a group"""

    def command(self, *args, **kwargs):
        default_command = kwargs.pop('default_command', False)
        if default_command and not args:
            kwargs['name'] = kwargs.get('name', 'termax/t')
        decorator = super(
            DefaultCommandGroup, self).command(*args, **kwargs)

        if default_command:
            def new_decorator(f):
                cmd = decorator(f)
                self.default_command = cmd.name
                return cmd

            return new_decorator

        return decorator

    def resolve_command(self, ctx, args):
        try:
            # test if the command parses
            return super(DefaultCommandGroup, self).resolve_command(ctx, args)
        except click.UsageError:
            # command did not parse, assume it is the default command
            args.insert(0, self.default_command)
            return super(DefaultCommandGroup, self).resolve_command(ctx, args)


def build_config(general: bool = False):
    """
    build_config: build the configuration for Termax.
    Args:
        general: a boolean indicating whether to build the general configuration only.
    :return:
    """
    configuration = Config()
    # configure the general configurations
    questions = [
        inquirer.List(
            "platform",
            message="What LLM (platform) are you using? (and we will set this as default)",
            choices=CONFIG_LLM_LIST,
        ),
    ]

    answers = inquirer.prompt(questions)
    selected_platform = answers["platform"].lower()
    general_config = {
        "platform": selected_platform,
        "auto_execute": True,
        "show_command": False
    }

    exe_questions = [
        inquirer.Confirm(
            "auto_execute",
            message="Do you want to execute the generated command automatically?",
            default=True,
        ),
        inquirer.Confirm(
            "show_command",
            message="Do you want to show the generated command?",
            default=False,
        )
    ]
    sub_answers = inquirer.prompt(exe_questions)
    general_config["auto_execute"] = sub_answers["auto_execute"]
    general_config["show_command"] = sub_answers["show_command"]

    # configure the platform specific configurations
    if not general:
        sub_answers = None
        if selected_platform == CONFIG_SEC_OPENAI:
            sub_questions = [
                inquirer.Text(
                    CONFIG_SEC_API_KEY,
                    message="What is your OpenAI API key?",
                )
            ]
            sub_answers = inquirer.prompt(sub_questions)

        default_config = {}
        platform = selected_platform
        if platform == CONFIG_SEC_OPENAI:
            default_config = {
                "model": "gpt-3.5-turbo",
                "platform": platform,
                "api_key": sub_answers[CONFIG_SEC_API_KEY] if sub_answers else None,
                'temperature': 0.7,
                'save': False,
                'auto_execute': False
            }

        # write the platform-related configuration to the file
        configuration.write_platform(default_config, platform=platform)

    # write the general configuration to the file
    configuration.write_general(general_config)


@click.group(cls=DefaultCommandGroup)
@click.version_option(version=termax.__version__)
def cli():
    pass


@cli.command(default_command=True)
@click.argument('text', nargs=-1)
def generate(text):
    """
    This function will call and generate the commands from LLM
    """
    memory = Memory()
    console = Console()
    text = " ".join(text)
    configuration = Config()

    # avoid the tokenizers parallelism issue
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'

    # check the configuration available or not
    if not os.path.exists(CONFIG_PATH):
        click.echo("Config file not found. Running config setup...")
        build_config()

    prompt = Prompt(memory)
    config_dict = configuration.read()
    platform = config_dict['general']['platform']
    if platform == CONFIG_SEC_OPENAI:
        model = OpenAIModel(
            api_key=config_dict['openai'][CONFIG_SEC_API_KEY], version=config_dict['openai']['model'],
            temperature=float(config_dict['openai']['temperature']),
            prompt=prompt.nl2commands(text)
        )
    elif platform == CONFIG_SEC_GEMINI:
        model = GeminiModel(
            api_key=config_dict['gemini'][CONFIG_SEC_API_KEY], version=config_dict['gemini']['model'],
            generation_config={
                'stop_sequences': config_dict['gemini']['stop_sequences'],
                'temperature': config_dict['gemini']['temperature'],
                'top_p': config_dict['gemini']['top_p'],
                'top_k': config_dict['gemini']['top_k'],
                'candidate_count': config_dict['gemini']['candidate_count'],
                'max_output_tokens': config_dict['gemini']['max_output_tokens']
            },
            prompt=prompt.nl2commands(text)
        )
    elif platform == CONFIG_SEC_CLAUDE:
        model = ClaudeModel(
            api_key=config_dict['claude'][CONFIG_SEC_API_KEY], version=config_dict['claude']['model'],
            generation_config={
                'stop_sequences': config_dict['claude']['stop_sequences'],
                'temperature': config_dict['claude']['temperature'],
                'top_p': config_dict['claude']['top_p'],
                'top_k': config_dict['claude']['top_k'],
                'max_tokens': config_dict['claude']['max_tokens']
            },
            prompt=prompt.nl2commands(text)
        )
    elif platform == CONFIG_SEC_QIANFAN:
        model = QianFanModel(
            api_key=config_dict['qianfan'][CONFIG_SEC_API_KEY], secret_key=config_dict['qianfan']['secret_key'],
            version=config_dict['qianfan']['model'],
            generation_config={
                'temperature': config_dict['qianfan']['temperature'],
                'top_p': config_dict['qianfan']['top_p'],
                'max_output_tokens': config_dict['qianfan']['max_output_tokens']
            },
            prompt=prompt.nl2commands(text)
        )
    elif platform == CONFIG_SEC_MISTRAL:
        model = MistralModel(
            api_key=config_dict['mistral'][CONFIG_SEC_API_KEY], version=config_dict['mistral']['model'],
            generation_config={
                'temperature': config_dict['mistral']['temperature'],
                'top_p': config_dict['mistral']['top_p'],
                'max_tokens': config_dict['mistral']['max_tokens']
            },
            prompt=prompt.nl2commands(text)
        )
    elif platform == CONFIG_SEC_QIANWEN:
        model = QianWenModel(
            api_key=config_dict['qianwen'][CONFIG_SEC_API_KEY], version=config_dict['qianwen']['model'],
            generation_config={
                'temperature': config_dict['qianwen']['temperature'],
                'top_p': config_dict['qianwen']['top_p'],
                'top_k': config_dict['qianwen']['top_k'],
                'stop': config_dict['qianwen']['stop'],
                'max_tokens': config_dict['qianwen']['max_tokens']
            },
            prompt=prompt.nl2commands(text)
        )
    else:
        raise ValueError(f"Platform {platform} not supported.")

        # generate the commands from the model, and execute if auto_execute is True
    with console.status(f"[cyan]Generating..."):
        command = model.to_command(text)

    if config_dict['general']['show_command'] == "True":
        console.log(f"Generated command: {command}")

    if config_dict['general']['auto_execute']:
        try:
            subprocess.run(command, shell=True, text=True)
        except KeyboardInterrupt:
            pass
        finally:
            # add the query to the memory, eviction with the max size of 100.
            if memory.count() > 100:  # TODO: should be able to set this number.
                memory.delete()

            if command != '':
                memory.add_query(queries=[{"query": text, "response": command}])


@cli.command()
@click.option('--general', '-g', is_flag=True, help="Set up the general configuration for Termax.")
def config(general):
    """
    Set up the global configuration for Termax.
    """
    build_config(general)