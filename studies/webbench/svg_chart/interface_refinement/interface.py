"""Read-only projection of a model-produced package onto its published plan interface."""


def planning_interface(package):
    interface = {"plan_schema": package["plan_schema"]}
    if "plan_documentation" in package:
        interface["plan_documentation"] = package["plan_documentation"]
    if len(package["examples"]) != 2:
        raise ValueError("Expected two package-authored worked examples")
    interface["examples"] = [
        {"description": item["description"], "plan": item["plan"]} for item in package["examples"]
    ]
    return interface
