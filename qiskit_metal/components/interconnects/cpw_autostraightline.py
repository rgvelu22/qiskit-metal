import numpy as np
from numpy.linalg import norm
from qiskit_metal import draw, Dict#, QComponent
from qiskit_metal.components import QComponent

class CpwAutoStraightLine(QComponent):

    """
    A non-meandered basic CPW that is auto-generated between 2 components.
    Designed to avoid self-collisions and collisions with components it is attached to.

    This class extends the `QComponent` class.

    Assumptions:

    1. Components are situated along xy axes in 2 dimensions. No rotation is allowed (yet). Their bounding boxes may
        not overlap, though they may be situated at arbitrary x and y provided these conditions are met.
    2. Pins point normal to qubits ("directly outward") and either in the x or y directions. They must not protrude
        from the exact corner of a component. [This last assumption has implications for 2-segment connections.]
    3. Intersection of CPWs with themselves or the qubits they stem from is prohibited. Intersection with other
        components/CPWs has not yet been considered.
    4. Components may not share an edge; a nonzero gap must be present between 2 adjacent qubits.
    5. CPWs must be attached to protruding leads via connectors head-on, not from the sides.
    """

    default_options = Dict(
        cpw_width='cpw_width',
        cpw_gap='cpw_gap',
        layer='1',
        leadin=Dict(
            start='22um',
            end='22um'
        )
    )
    """Default options"""
    
    def getpts(self, startpin: str, endpin: str, width: float, segments: int, leadstart: float, leadend: float, constaxis=0, constval=0) -> list:
        """
        Generate the list of 2D coordinates comprising a CPW between startpin and endpin.

        Args:
            startpin (str): Name of startpin
            endpin (str): Name of endpin
            width (float): Width of CPW in mm
            segments (int): Number of segments in the CPW, not including leadin and leadout. Ranges from 1 to 3.
            leadstart (float): Length of first CPW segment originating at startpin
            leadend (float): Length of final CPW segment ending at endpin
            constaxis (int, optional): In the case of 3 segment CPWs, the constant axis of the line that both
                leadin and leadout must connect to. Example: If x = 3, the constant axis (x) is 0. Defaults to 0.
            constval (int, optional): In the case of 3 segment CPWs, the constant numerical value of the line
                that both leadin and leadout must connect to. Example: If x = 3, the constant value is 3. Defaults to 0.

        Returns:
            List: [np.array([x0, y0]), np.array([x1, y1]), np.array([x2, y2])] where xi, yi are vertices of CPW.
        """
        if segments == 1:
            # Straight across or up and down; no additional points necessary
            midcoords = []
        elif segments == 2:
            # Choose between 2 diagonally opposing corners so that CPW doesn't trace back on itself
            corner1 = np.array([(startpin.middle + startpin.normal * (width / 2 + leadstart))[0], 
                                (endpin.middle + endpin.normal * (width / 2 + leadend))[1]])
            corner2 = np.array([(endpin.middle + endpin.normal * (width / 2 + leadend))[0], 
                                (startpin.middle + startpin.normal * (width / 2 + leadstart))[1]])
            startc1 = np.dot(corner1 - (startpin.middle + startpin.normal * (width / 2 + leadstart)), startpin.normal)
            endc1 = np.dot(corner1 - (endpin.middle + endpin.normal * (width / 2 + leadend)), endpin.normal)
            startc2 = np.dot(corner2 - (startpin.middle + startpin.normal * (width / 2 + leadstart)), startpin.normal)
            endc2 = np.dot(corner2 - (endpin.middle + endpin.normal * (width / 2 + leadend)), endpin.normal)
            # If both pins' normal vectors point towards one of the corners, pick that corner
            if (startc1 > 0) and (endc1 > 0):
                midcoords = [corner1]
            elif (startc2 > 0) and (endc2 > 0):
                midcoords = [corner2]
            elif min(startc1, endc1) >= 0:
                midcoords = [corner1]
            else:
                midcoords = [corner2]
        elif segments == 3:
            # Connect startpin and endpin to long segment at constaxis
            # 2 additional intermediate points needed to achieve this
            if constaxis == 0:
                # Middle segment lies on the line x = c for some constant c
                midcoord_start = np.array([constval, (startpin.middle + startpin.normal * (width / 2 + leadstart))[1]])
                midcoord_end = np.array([constval, (endpin.middle + endpin.normal * (width / 2 + leadend))[1]])
            else:
                # Middle segment lies on the line y = d for some constant d
                midcoord_start = np.array([(startpin.middle + startpin.normal * (width / 2 + leadstart))[0], constval])
                midcoord_end = np.array([(endpin.middle + endpin.normal * (width / 2 + leadend))[0], constval])
            midcoords = [midcoord_start, midcoord_end]
        startpts = [startpin.middle, startpin.middle + startpin.normal * (width / 2 + leadstart)]
        endpts = [endpin.middle + endpin.normal * (width / 2 + leadend), endpin.middle]
        return startpts + midcoords + endpts

    def totlength(self, pts: list) -> float:
        """Get total length of all line segments in a given CPW."""
        return sum(norm(pts[i] - pts[i - 1]) for i in range(1, len(pts)))
    
    def make(self):
        """
        Use user-specified parameters and geometric orientation of components to determine whether the CPW connecting
        the pins on either end requires 1, 2, or 3 segments. Preference given to shorter paths and paths that flow
        with the leadin and leadout directions rather than turning immediately at 90 deg.

        Keepout region along x and y directions specified for CPWs that wrap around outer perimeter of overall bounding
        box of both components.
        """
        
        self.__pts = [] # list of 2D numpy arrays containing vertex locations

        p = self.p # parsed options

        w = p.cpw_width
        leadstart = p.leadin.start
        leadend = p.leadin.end
        keepoutx = 0.2
        keepouty = 0.2

        component_start = p.pin_inputs['start_pin']['component']
        pin_start = p.pin_inputs['start_pin']['pin']
        component_end = p.pin_inputs['end_pin']['component']
        pin_end = p.pin_inputs['end_pin']['pin']

        # Starting and ending pin (connector) dictionaries
        connector1 = self.design.components[component_start].pins[pin_start]
        connector2 = self.design.components[component_end].pins[pin_end]

        n1 = connector1.normal
        n2 = connector2.normal

        m1 = connector1.middle
        m2 = connector2.middle

        # Coordinates of bounding box for each individual component
        minx1, miny1, maxx1, maxy1 = self.design.components[component_start].qgeometry_bounds()
        minx2, miny2, maxx2, maxy2 = self.design.components[component_end].qgeometry_bounds()

        # Coordinates of overall bounding box which includes both components
        minx, miny = min(minx1, minx2), min(miny1, miny2)
        maxx, maxy = max(maxx1, maxx2), max(maxy1, maxy2)

        # Normdot is dot product of normal vectors
        normdot = np.dot(n1, n2)

        if normdot == -1:
            # Modify CPW endpoints to include mandatory w / 2 leadin plus user defined leadin
            m1ext = m1 + n1 * (w / 2 + leadstart)
            m2ext = m2 + n2 * (w / 2 + leadend)
            # Alignment is between displacement of modified positions (see above) and normal vector
            alignment = np.dot((m2ext - m1ext) / norm(m2ext - m1ext), n1)
            if alignment == 1:
                # Normal vectors point directly at each other; no obstacles in between
                # Connect with single segment; generalizes to arbitrary angles with no snapping
                self.__pts = self.getpts(connector1, connector2, w, 1, leadstart, leadend)
            elif alignment > 0:
                # Displacement partially aligned with normal vectors
                # Connect with antisymmetric 3-segment CPW
                if n1[1] == 0:
                    # Normal vectors horizontal
                    if minx2 < maxx1:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, (minx2 + maxx1) / 2)
                    else:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, (minx1 + maxx2) / 2)
                else:
                    # Normal vectors vertical
                    if miny2 < maxy1:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, (miny2 + maxy1) / 2)
                    else:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, (miny1 + maxy2) / 2)
            elif alignment == 0:
                # Displacement orthogonal to normal vectors
                # Connect with 1 segment
                self.__pts = self.getpts(connector1, connector2, w, 1, leadstart, leadend)
            elif alignment < 0:
                # Normal vectors on opposite sides of squares
                if n1[1] == 0:
                    # Normal vectors horizontal
                    if maxy1 < miny2:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, (maxy1 + miny2) / 2)
                    elif maxy2 < miny1:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, (maxy2 + miny1) / 2)
                    else:
                        # Gap running only vertically -> must wrap around with shorter of 2 possibilities
                        # pts_top represents 3-segment CPW running along top edge of overall bounding box
                        # pts_bott represents 3-segment CPW running along bottom edge of overall bounding box
                        pts_top = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, maxy + keepouty)
                        pts_bott = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, miny - keepouty)
                        if self.totlength(pts_top) < self.totlength(pts_bott):
                            self.__pts = pts_top
                        else:
                            self.__pts = pts_bott
                else:
                    # Normal vectors vertical
                    if maxx1 < minx2:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, (maxx1 + minx2) / 2)
                    elif maxx2 < minx1:
                        self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, (maxx2 + minx1) / 2)
                    else:
                        # Gap running only horizontally -> must wrap around with shorter of 2 possibilities
                        # pts_left represents 3-segment CPW running along left edge of overall bounding box
                        # pts_right represents 3-segment CPW running along right edge of overall bounding box
                        pts_left = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, minx - keepoutx)
                        pts_right = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, maxx + keepoutx)
                        if self.totlength(pts_left) < self.totlength(pts_right):
                            self.__pts = pts_left
                        else:
                            self.__pts = pts_right
        elif normdot == 0:
            # Normal vectors perpendicular to each other
            if (m1[0] in [minx, maxx]) and (m2[1] in [miny, maxy]):
                # Both pins on perimeter of overall bounding box, but not at corner
                self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
            elif (m1[1] in [miny, maxy]) and (m2[0] in [minx, maxx]):
                # Both pins on perimeter of overall bounding box, but not at corner
                self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
            elif (m1[0] not in [minx, maxx]) and (m2[0] not in [minx, maxx]) and (m1[1] not in [miny, maxy]) and (m2[1] not in [miny, maxy]):
                # Neither pin lies on perimeter of overall bounding box
                # Always possible to connect with at most 2 segments
                if (m1[0] == m2[0]) or (m1[1] == m2[1]):
                    # Connect directly with 1 segment
                    self.__pts = self.getpts(connector1, connector2, w, 1, leadstart, leadend)
                else:
                    # Connect with 2 segments
                    self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
            elif (m1[0] in [minx, maxx]) or (m1[1] in [miny, maxy]):
                # Pin 1 lies on boundary of overall bounding box but pin 2 does not
                if m1[0] in [minx, maxx]:
                    # Pin 1 on left or right boundary, pointing left or right, respectively
                    if n2[1] > 0:
                        # Pin 2 pointing up
                        if miny1 > maxy2:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, maxy + keepouty)
                    else:
                        # Pin 2 pointing down
                        if miny2 > maxy1:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, miny - keepouty)
                elif m1[1] in [miny, maxy]:
                    # Pin 1 on bottom or top boundary, pointing down or up, respectively
                    if n2[0] < 0:
                        # Pin 2 pointing left
                        if minx2 > maxx1:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, minx - keepoutx)
                    else:
                        # Pin 2 pointing right
                        if minx1 > maxx2:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, maxx + keepoutx)
            elif (m2[0] in [minx, maxx]) or (m2[1] in [miny, maxy]):
                # Pin 2 lies on boundary of overall bounding box but pin 1 does not
                if m2[0] in [minx, maxx]:
                    # Pin 2 on left or right boundary, pointing left or right, respectively
                    if n1[1] > 0:
                        # Pin 1 pointing up
                        if miny2 > maxy1:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, maxy + keepouty)
                    else:
                        # Pin 1 pointing down
                        if miny1 > maxy2:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, miny - keepouty)
                elif m2[1] in [miny, maxy]:
                    # Pin 2 on bottom or top boundary, pointing down or up, respectively
                    if n1[0] < 0:
                        # Pin 1 pointing left
                        if minx1 > maxx2:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, minx - keepoutx)
                    else:
                        # Pin 1 pointing right
                        if minx2 > maxx1:
                            self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                        else:
                            self.__pts = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, maxx + keepoutx)
        else:
            # Normal vectors pointing in same direction
            if ((m1[0] == m2[0]) or (m1[1] == m2[1])) and (np.dot(n1, m2 - m1) == 0):
                # Connect directly with 1 segment
                self.__pts = self.getpts(connector1, connector2, w, 1, leadstart, leadend)
            elif n1[1] == 0:
                # Normal vectors horizontal
                if (m1[1] > maxy2) or (m2[1] > maxy1):
                    # Connect with 2 segments
                    self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                else:
                    # Must wrap around with shorter of the 2 following possibilities:
                    # pts_top represents 3-segment CPW running along top edge of overall bounding box
                    # pts_bott represents 3-segment CPW running along bottom edge of overall bounding box
                    pts_top = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, maxy + keepouty)
                    pts_bott = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 1, miny - keepouty)
                    if self.totlength(pts_top) < self.totlength(pts_bott):
                        self.__pts = pts_top
                    else:
                        self.__pts = pts_bott
            else:
                # Normal vectors vertical
                if (m1[0] > maxx2) or (m2[0] > maxx1):
                    # Connect with 2 segments
                    self.__pts = self.getpts(connector1, connector2, w, 2, leadstart, leadend)
                else:
                    # Must wrap around with shorter of the 2 following possibilities:
                    # pts_left represents 3-segment CPW running along left edge of overall bounding box
                    # pts_right represents 3-segment CPW running along right edge of overall bounding box
                    pts_left = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, minx - keepoutx)
                    pts_right = self.getpts(connector1, connector2, w, 3, leadstart, leadend, 0, maxx + keepoutx)
                    if self.totlength(pts_left) < self.totlength(pts_right):
                        self.__pts = pts_left
                    else:
                        self.__pts = pts_right

        # Create CPW geometry using list of vertices
        line = draw.LineString(self.__pts)

        # Add CPW to elements table
        self.add_qgeometry('path', {'center_trace': line}, width=p.cpw_width, layer=p.layer)
        self.add_qgeometry('path', {'gnd_cut': line}, width=p.cpw_width+2*p.cpw_gap, subtract = True)

        # Create new pins for the CPW itself
        self.add_pin('auto_cpw_start', connector1.points[::-1], p.cpw_width)
        self.add_pin('auto_cpw_end', connector2.points[::-1], p.cpw_width)

        # Add to netlist
        self.design.connect_pins(
            self.design.components[component_start].id, pin_start, self.id, 'auto_cpw_start')
        self.design.connect_pins(
            self.design.components[component_end].id, pin_end, self.id, 'auto_cpw_end')