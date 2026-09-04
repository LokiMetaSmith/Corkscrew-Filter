"""
OpenAuto EM Live Bridge — KiCad 7 / 8 / 9 / 10 Action Plugin
"""

from .action_openauto_em import OpenAutoEMLiveActionPlugin

# Instantiates and registers the action plugin with KiCad's pcbnew inside KiCad GUI
try:
    import wx
    if wx.GetApp() is not None:
        OpenAutoEMLiveActionPlugin().register()
except Exception:
    pass

