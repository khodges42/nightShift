### Future Ideas
Not to implement until we get successful long running runs.

## I am realizing "templates" are abstracted from the user
* I think templates will be a first class citizen, a package for deployments, and a harness for performance tests
* These should live external to nightshift/project_templates as users will likely create their own 
* one solution would be to reference two directories when looking up templates, builtin ones will be in nightshift/project_templates or users can define a templates directory in their nightshift config

## nightshift config
* store user settings in ~/.nightshift/config.yaml
* things like templates folder (can also live here)
* maybe this is later

## A way to easily make A/B tests to benchmark models?
* Right now I can do this manually, for example I want to run the tutorial-deaddrop with qwen3.6:27b as the planner and qwen2.5-coder:14b as the coder, and another with qwen3.6:27b as both, etc.
* Maybe there is a way to make it easier to do that, possibly by creating a template that can be controlled by a larger multi-run file?
* This is probably for way later.
