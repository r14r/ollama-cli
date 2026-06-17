# PyOxidizer packaging configuration for ollama-cli

def make_dist():
    return default_python_distribution()

def make_exe(dist):
    policy = dist.make_python_packaging_policy()
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "filesystem-relative:lib"

    config = dist.make_python_interpreter_config()
    config.run_module = "ollama_cli"

    exe = dist.to_python_executable(
        name="ollama-cli",
        packaging_policy=policy,
        config=config,
    )

    # Package current application and its dependencies
    exe.add_python_resources(exe.pip_install(["."]))

    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files

register_target("dist", make_dist)
register_target("exe", make_exe, depends=["dist"])
register_target("resources", make_embedded_resources, depends=["exe"])
register_target("install", make_install, depends=["exe"])

resolve_targets()
