from pythonforandroid.recipe import (
    IncludedFilesBehaviour,
    PythonRecipe
)


class OpenpaperworkcoreRecipe(
            IncludedFilesBehaviour,
            PythonRecipe
        ):
    version = 'current'
    depends = ['setuptools']
    src_filename = "../../../openpaperwork-core"
    name = "openpaperwork_core"

    call_hostpython_via_targetpython = False
    install_in_hostpython = True


recipe = OpenpaperworkcoreRecipe()
