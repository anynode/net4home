Logger: homeassistant.setup
Quelle: setup.py:344
Erstmals aufgetreten: 17:23:17 (1 Vorkommnis)
Zuletzt protokolliert: 17:23:17

Setup failed for custom integration 'net4home': Unable to import component: Exception importing custom_components.net4home
Traceback (most recent call last):
  File "/usr/src/homeassistant/homeassistant/loader.py", line 1053, in _get_component
    ComponentProtocol, importlib.import_module(self.pkg_path)
                       ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/src/homeassistant/homeassistant/util/loop.py", line 201, in protected_loop_func
    return func(*args, **kwargs)
  File "/usr/local/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/config/custom_components/net4home/__init__.py", line 9, in <module>
    from .api import Net4HomeClient
  File "/config/custom_components/net4home/api.py", line 2
    sub N4HBUS_DoInit($) {
        ^^^^^^^^^^^^^
SyntaxError: invalid syntax

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/usr/src/homeassistant/homeassistant/loader.py", line 993, in async_get_component
    comp = await self.hass.async_add_import_executor_job(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self._get_component, True
        ^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/concurrent/futures/thread.py", line 59, in run
    result = self.fn(*self.args, **self.kwargs)
  File "/usr/src/homeassistant/homeassistant/loader.py", line 1064, in _get_component
    raise ImportError(f"Exception importing {self.pkg_path}") from err
ImportError: Exception importing custom_components.net4home

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/usr/src/homeassistant/homeassistant/loader.py", line 1053, in _get_component
    ComponentProtocol, importlib.import_module(self.pkg_path)
                       ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/src/homeassistant/homeassistant/util/loop.py", line 201, in protected_loop_func
    return func(*args, **kwargs)
  File "/usr/local/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/config/custom_components/net4home/__init__.py", line 9, in <module>
    from .api import Net4HomeClient
  File "/config/custom_components/net4home/api.py", line 2
    sub N4HBUS_DoInit($) {
        ^^^^^^^^^^^^^
SyntaxError: invalid syntax

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/usr/src/homeassistant/homeassistant/setup.py", line 344, in _async_setup_component
    component = await integration.async_get_component()
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/src/homeassistant/homeassistant/loader.py", line 1013, in async_get_component
    self._component_future.result()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/src/homeassistant/homeassistant/loader.py", line 1005, in async_get_component
    comp = self._get_component()
  File "/usr/src/homeassistant/homeassistant/loader.py", line 1064, in _get_component
    raise ImportError(f"Exception importing {self.pkg_path}") from err
ImportError: Exception importing custom_components.net4home