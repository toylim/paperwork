from pythonforandroid.recipe import (
    IncludedFilesBehaviour,
    PythonRecipe
)


class PaperworkbackendRecipe(
            IncludedFilesBehaviour,
            PythonRecipe
        ):
    version = 'current'
    depends = ['setuptools', 'pillow']
    src_filename = "../../../paperwork-backend"
    name = "paperwork_backend"

    call_hostpython_via_targetpython = False
    install_in_hostpython = True


recipe = PaperworkbackendRecipe()
