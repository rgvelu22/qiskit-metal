# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# Tree model for Ansys Q3D renderer

from PySide2.QtWidgets import QTreeView, QWidget

from qiskit_metal._gui.widgets.bases.dict_tree_base import QTreeModel_Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qiskit_metal._gui.main_window.orig.main_window import MetalGUI


class RendererQ3D_Model(QTreeModel_Base):
    """Tree model for Ansys Q3D renderer.

    Args:
        QTreeModel_Base (QAbstractItemModel): Base class for nested dicts
    """

    def __init__(self, parent: QWidget, gui: 'MetalGUI', view: QTreeView):
        """Editable table with drop-down rows for Q3D renderer options.
        Organized as a tree model where child nodes are more specific
        properties of a given parent node.

        Args:
            parent (QWidget): The parent widget
            gui (MetalGUI): The main user interface
            view (QTreeView): View corresponding to a tree structure
        """
        super().__init__(parent=parent,
                         gui=gui,
                         view=view,
                         child='Q3D renderer')

    @property
    def data_dict(self) -> dict:
        """Return a reference to the (nested) dictionary containing the
        data."""
        return self.design.renderers.q3d.options