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

from qiskit_metal.designs import QDesign  # pylint: disable=unused-import
from . import EigenmodeSim

from ... import Dict


# TODO: eliminate every reference to "renderer" in this file
#  then change inheritance from QAnalysisRenderer to QAnalysis
class EPRanalysis(EigenmodeSim):
    """From an input eigenmode dataset, apply the Energy Participation Ratio analysis method.

    Default Setup:
        * junctions (Dict):
            * keys (str): Name of each Non-linear (Josephson) junction to consider in EPR
            * values (Dict):
                * Lj_variable (str): Name of renderer variable that specifies junction inductance.
                * Cj_variable (str): Name of renderer variable that specifies junction capacitance.
                * rect (str): Name of renderer rectangle on which the lumped boundary condition
                    is defined.
                * line (str): Name of renderer line spanning the length of rect
                    (voltage, orientation, ZPF).
        * dissipatives (Dict):
            * keys (str): Categories of dissipatives that can appear in the syste. Possible keys
                are: 'dielectrics_bulk', 'dielectric_surfaces', 'resistive_surfaces', 'seams'.
            * values (list of str): Names of the shapes composing that dissipative.
        * cos_trunc (int): truncation of the cosine function
        * fock_trunc (int): truncation of the fock
        * sweep_variable (str): Variable to sweep during EPR

    Data Labels:
        * energy_elec (float): Name given to the current sweep.
        * energy_mag (float): Impedence matrix.
        * energy_elec_sub (float): Admittance matrix.

    """
    default_setup = Dict(epr=Dict(junctions=Dict(
        jj=Dict(Lj_variable='Lj', Cj_variable='Cj', rect='', line='')),
                                  dissipatives=Dict(dielectrics_bulk=['main']),
                                  cos_trunc=8,
                                  fock_trunc=7,
                                  sweep_variable='Lj'))
    """Default setup."""

    # supported labels for data generated from the simulation
    data_labels = ['energy_elec', 'energy_mag', 'energy_elec_sub']
    """Default data labels."""

    def __init__(self, design: 'QDesign', renderer_name: str = 'hfss'):
        """Performs Energy Participation Ratio (EPR) analysis on a simulated or
        user-provided eigenmode matrix.

        Args:
            design (QDesign): Pointer to the main qiskit-metal design.
                Used to access the Qrenderer.
            renderer_name (str, optional): Which renderer to use. Defaults to 'hfss'.
        """
        # set design and renderer
        super().__init__(design, renderer_name)

        # TODO: define the input variables == define the output variables of the
        #  EigenmodeSim class. this will likely require to find them inside pinfo

    @property
    def energy_elec(self) -> float:
        """Getter

        Returns:
            float: Electric field energy stored in the system based on the eigenmode results.
        """
        return self.get_data('energy_elec')

    @energy_elec.setter
    def energy_elec(self, data: float):
        """Setter

        Args:
            data (float): Electric field energy stored in the system based on the eigenmode results.
        """
        if not isinstance(data, float):
            self.logger.warning(
                'Unuspported type %s. Only accepts float. Please try again.',
                {type(data)})
            return
        self.set_data('energy_elec', data)

    @property
    def energy_mag(self) -> float:
        """Getter

        Returns:
            float: Magnetic field energy stored in the system based on the eigenmode results.
        """
        return self.get_data('energy_mag')

    @energy_mag.setter
    def energy_mag(self, data: float):
        """Setter

        Args:
            data (float): Magnetic field energy stored in the system based on the eigenmode results.
        """
        if not isinstance(data, float):
            self.logger.warning(
                'Unuspported type %s. Only accepts float. Please try again.',
                {type(data)})
            return
        self.set_data('energy_mag', data)

    @property
    def energy_elec_sub(self) -> float:
        """Getter

        Returns:
            float: Electric field energy stored in the substrate based on the eigenmode results.
        """
        return self.get_data('energy_elec_sub')

    @energy_elec_sub.setter
    def energy_elec_sub(self, data: float):
        """Setter

        Args:
            data (float): Electric field energy stored in the substrate based
                on the eigenmode results.
        """
        if not isinstance(data, float):
            self.logger.warning(
                'Unuspported type %s. Only accepts float. Please try again.',
                {type(data)})
            return
        self.set_data('energy_elec_sub', data)

    def run(self, *args, **kwargs):
        """Executes sequentually the system capacitance simulation and lom extraction
        executing the methods LumpedElementsSim.run_sim(`*args`, `**kwargs`) and LOManalysis.run_epr().
        For imput parameter, see documentation for LumpedElementsSim.run_sim().

        Returns:
            (dict): Pass numbers (keys) and respective lump oscillator information (values).
        """
        self.run_sim(*args, **kwargs)
        return self.run_epr()

    def run_epr(self, no_junctions=False):
        """Executes the epr analysis from the extracted eigemode,
        and based on the setup values.
        """
        # wipe data from the previous run (if any)
        self.clear_data(self.data_labels)

        self.get_stored_energy(no_junctions)
        if not no_junctions:
            self.run_analysis()
            self.spectrum_analysis(self.setup.epr.cos_trunc,
                                   self.setup.epr.fock_trunc)
            self.report_hamiltonian(self.setup.epr.sweep_variable)

    # TODO: all the epr methods should not use the renderer. Now they are forced to because of the
    #  pyEPR dependency from pinfo. pinfo however is Ansys specific and cannot be generalized as-is
    #  Therefore we need to eliminate pyEPR dependency on pinfo, or re-implement in qiskit-metal

    def epr_start(self, no_junctions=False):
        """
        Initialize epr package.
        """
        # pandas cannot handle Dict so need to convert Dict to dict
        system = dict()
        s = self.setup.epr
        system['junctions'] = {} if no_junctions else {
            k: dict(v) for (k, v) in s.junctions.items()
        }
        system['dissipatives'] = dict(s.dissipatives)
        self.renderer.epr_start(**system)
        return system

    def get_stored_energy(self, no_junctions=False):
        """Calculate the energy stored in the system based on the eigenmode results.
        """
        # execute EPR and energy extraction
        self.energy_elec, self.energy_elec_sub, self.energy_mag = \
            self.renderer.epr_get_stored_energy(**self.epr_start(no_junctions))

        # present a human-friendly output
        print(f"""
        energy_elec_all       = {self.energy_elec}
        energy_elec_substrate = {self.energy_elec_sub}
        EPR of substrate = {self.energy_elec_sub / self.energy_elec * 100 :.1f}%

        energy_mag    = {self.energy_mag}
        energy_mag % of energy_elec_all  = {self.energy_mag / self.energy_elec * 100 :.1f}%
        """)

    def run_analysis(self):
        """Short-cut to the same-name method found in renderers.ansys_renderer.py.
        Eventually, the analysis code needs to be only here, and the renderer method deprecated.
        """
        self.renderer.epr_run_analysis()

    def spectrum_analysis(self, cos_trunc: int = 8, fock_trunc: int = 7):
        """Short-cut to the same-name method found in renderers.ansys_renderer.py.
        Eventually, the analysis code needs to be only here, and the renderer method deprecated.
        """
        self.renderer.epr_spectrum_analysis(cos_trunc, fock_trunc)

    def report_hamiltonian(self, sweep_variable, numeric=True):
        """Short-cut to the same-name method found in renderers.ansys_renderer.py.
        Eventually, the analysis code needs to be only here, and the renderer method deprecated.
        """
        self.renderer.epr_report_hamiltonian(sweep_variable, numeric)

    def get_frequencies(self):
        """Short-cut to the same-name method found in renderers.ansys_renderer.py.
        Eventually, the analysis code needs to be only here, and the renderer method deprecated.
        """
        system = self.epr_start(no_junctions=True)
        return self.renderer.epr_get_frequencies(**system)
