import os
import win32com.client
import numpy as np

DOCTYPE_MAPPING = {
    'magnetics': 1,
    'electrostatics': 2,
    'heat': 3,
    'current': 4,
}

DOCTYPE_PREFIX_MAPPING = {
    0: 'm',
    'magnetics': 'm',
    1: 'e',
    'electrostatics': 'e',
    2: 'h',
    'heat': 'h',
    3: 'c',
    'current': 'c',
}

PREFIX_DOCTYPE_MAPPING = {
    'm': 'magnetics',
    'e': 'electrostatics',
    'h': 'heat',
    'c': 'current',
}


class FEMMSession:
    """A simple wrapper around FEMM 4.2."""

    doctype_prefix = None

    def __init__(self):
        self.__to_femm = win32com.client.Dispatch('femm.ActiveFEMM')
        self.set_current_directory()
        self.pre = PreprocessorAPI(self)
        self.post = PostProcessorAPI(self)

    def _add_doctype_prefix(self, string):
        return self.doctype_prefix + string

    def call_femm(self, string, add_doctype_prefix=False):
        """Call a given command string using ``mlab2femm``."""

        if add_doctype_prefix:
            res = self.__to_femm.mlab2femm(self._add_doctype_prefix(string))
        else:
            res = self.__to_femm.mlab2femm(string)
        if len(res) == 0:
            res = []
        elif res[0] == 'e':
            raise Exception(res)
        else:
            res = eval(res)
        if len(res) == 1:
            res = res[0]
        return res

    def call_femm_noeval(self, string):
        """Call a given command string using ``mlab2femm`` without eval."""

        self.__to_femm(string)

    def call_femm_with_args(self, command, *args, add_doctype_prefix=True):
        """Call a given command string using ``mlab2femm`` and parse the args."""

        if add_doctype_prefix:
            return self.call_femm(self._add_doctype_prefix(command) + self._parse_args(args))
        return self.call_femm(command + self._parse_args(args))

    @staticmethod
    def _fix_path(path):
        """Replace \\ and // with a single forward slash."""

        return path.replace('\\', '/').replace('//', '/')

    @staticmethod
    def _parse_args(args):
        """Convert each argument into a string and then join them by commas."""

        args_string = ', '.join(map(lambda arg: f'"{arg}"' if isinstance(arg, str) else str(arg), args))
        return f'({args_string})'

    @staticmethod
    def _quote(string):
        return f'"{string}"'

    def set_current_directory(self):
        """Set the current working directory using ``os.getcmd()``."""

        path_of_current_directory = self._fix_path(os.getcwd())
        self.call_femm(f'setcurrentdirectory({self._quote(path_of_current_directory)})')

    def new_document(self, doctype):
        """Creates a new preprocessor document and opens up a new preprocessor window. Specify doctype
        to be 0 for a magnetics problem, 1 for an electrostatics problem, 2 for a heat flow problem,
        or 3 for a current flow problem. An alternative syntax for this command is create(doctype)."""

        mode = DOCTYPE_MAPPING[doctype] if isinstance(doctype, str) else doctype
        self.call_femm(f'newdocument({mode})')
        self.set_mode(mode)

    def quit(self):
        """Close all documents and exit the the Interactive Shell at the end of
        the currently executing Lua script."""

        self.call_femm('quit()')

    def set_mode(self, doctype):
        self.doctype_prefix = DOCTYPE_PREFIX_MAPPING[doctype]

    @property
    def mode(self):
        return PREFIX_DOCTYPE_MAPPING[self.doctype_prefix]


class BaseAPI:

    mode_prefix = None

    def __init__(self, session):
        self.session = session

    def _add_mode_prefix(self, string):
        return f'{self.mode_prefix}_{string}'

    def _call_femm(self, string, add_doctype_prefix=False):
        return self.session.call_femm(f'{self._add_mode_prefix(string)}()', add_doctype_prefix=add_doctype_prefix)

    def _call_femm_with_args(self, string, *args):
        return self.session.call_femm_with_args(self._add_mode_prefix(string), *args)


class PreprocessorAPI(BaseAPI):
    """Preprocessor API"""

    mode_prefix = 'i'

    def close(self):
        """Closes current magnetics preprocessor document and
        destroys magnetics preprocessor window."""

        self._call_femm('close', add_doctype_prefix=True)

    # Utilities

    def draw_polyline_pattern(self, points, center=None, repeat=None):
        change_in_angle = (2 * np.pi) / repeat
        ret = [points]
        for i in range(repeat):
            if i == 0:
                self.draw_polyline(points)
            else:
                pattern_angle = change_in_angle * i
                rotation_matrix = np.array([[np.cos(pattern_angle), -np.sin(pattern_angle)],
                                            [np.sin(pattern_angle), np.cos(pattern_angle)]])
                new_points = [point - np.array(center) for point in points]
                new_points = [np.dot(rotation_matrix, np.array(point).reshape(2, 1)).reshape(2) for point in new_points]
                new_points = [point + np.array(center) for point in new_points]
                new_points = [np.round(point, decimals=5).tolist() for point in new_points]
                self.draw_polyline(new_points)
                ret.append(new_points)
        return ret

    def draw_arc_pattern(self, x1, y1, x2, y2, angle, max_seg, center=None, repeat=None):
        change_in_angle = (2 * np.pi) / repeat
        for i in range(repeat):
            if i == 0:
                self.draw_arc(x1, y1, x2, y2, angle, max_seg)
            else:
                pattern_angle = change_in_angle * i
                rotation_matrix = np.array([[np.cos(pattern_angle), -np.sin(pattern_angle)],
                                            [np.sin(pattern_angle), np.cos(pattern_angle)]])
                points = [[x1, y1], [x2, y2]]
                new_points = [point - np.array(center) for point in points]
                new_points = [np.dot(rotation_matrix, np.array(point).reshape(2, 1)).reshape(2) for point in new_points]
                new_points = [point + np.array(center) for point in new_points]
                new_points = [np.round(point, decimals=5).tolist() for point in new_points]
                self.draw_arc(*new_points[0], *new_points[1], angle, max_seg)

    # Object Add/Remove Commands

    def add_node(self, x, y):
        """Add a new node at x, y."""

        self._call_femm_with_args('addnode', x, y)

    def add_segment(self, x1, y1, x2, y2):
        """Add a new line segment from node closest to (x1, y1) to node closest to (x2, y2)."""

        self._call_femm_with_args('addsegment', x1, y1, x2, y2)

    def add_block_label(self, x, y):
        """Add a new block label at (x, y)."""

        self._call_femm_with_args('addblocklabel', x, y)

    def add_arc(self, x1, y1, x2, y2, angle, max_seg):
        """Add a new arc segment from the nearest node to (x1, y1) to the nearest node to
        (x2, y2) with angle ‘angle’ divided into ‘max_seg’ segments"""

        self._call_femm_with_args('addarc', x1, y1, x2, y2, angle, max_seg)

    def draw_line(self, x1, y1, x2, y2):
        """Adds nodes at (x1,y1) and (x2,y2) and adds a line between the nodes."""

        self.add_node(x1, y1)
        self.add_node(x2, y2)
        self.add_segment(x1, y1, x2, y2)

    def draw_polyline(self, points_list):
        """Adds nodes at each of the specified points and connects them with segments.
        ``points_list`` will look something like [[x1, y1], [x2, y2], ...]"""

        for i, current_point in enumerate(points_list):
            # Add each node.
            self.add_node(*current_point)
            if 0 < i < len(points_list):
                # Draw lines between each node.
                previous_point = points_list[i-1]
                self.draw_line(*previous_point, *current_point)

    def draw_polygon(self, points_list):
        """Adds nodes at each of the specified points and connects them with
        segments to form a closed contour."""

        self.draw_polyline(points_list)
        # Connect the first and the last nodes.
        self.draw_line(*points_list[0], *points_list[::-1][0])

    def draw_arc(self, x1, y1, x2, y2, angle, max_seg):
        """Adds nodes at (x1,y1) and (x2,y2) and adds an arc of the specified
        angle and discretization connecting the nodes."""

        self.add_node(x1, y1)
        self.add_node(x2, y2)
        self.add_arc(x1, y1, x2, y2, angle, max_seg)

    def draw_circle(self, x, y, radius, max_seg):
        """Adds nodes at the top and bottom points of a circle centred at
        (x1, y1) with the provided radius."""

        top_point = (x, y + (radius / 2))
        bottom_point = (x, y - (radius / 2))
        self.draw_arc(*top_point, *bottom_point, 180, max_seg)
        self.draw_arc(*bottom_point, *top_point, 180, max_seg)

    def draw_annulus(self, x, y, inner_radius=None, outer_radius=None, max_seg=None):
        """Creates two concentric circles with the outer and inner radii provided.
        The same ``max_seg`` value is used for both circles."""

        self.draw_circle(x, y, inner_radius, max_seg)
        self.draw_circle(x, y, outer_radius, max_seg)

    def draw_rectangle(self, x1, y1, x2, y2):
        """Adds nodes at the corners of a rectangle defined by the points (x1, y1) and
        (x2, y2), then adds segments connecting the corners of the rectangle."""

        self.draw_line(x1, y1, x2, y1)
        self.draw_line(x2, y1, x2, y2)
        self.draw_line(x2, y2, x1, y2)
        self.draw_line(x1, y2, x1, y1)

    def delete_selected(self):
        """Delete all selected objects."""

        self._call_femm('deleteselected')

    def delete_selected_nodes(self):
        """Delete selected nodes."""

        self._call_femm('deleteselectednodes')

    def delete_selected_labels(self):
        """Delete selected labels."""

        self._call_femm('deleteselectedlabels')

    def delete_selected_segments(self):
        """Delete selected segments."""

        self._call_femm('deleteselectedsegments')

    def delete_selected_arc_segments(self):
        """Delete selected arc segments."""

        self._call_femm('deleteselectedarcsegments')

    # Geometry Selection Commands

    def clear_selected(self):
        ...

    def select_segment(self):
        ...

    def select_node(self):
        ...

    def select_label(self):
        ...

    def select_arc_segment(self):
        ...

    def select_group(self):
        ...

    # Object Labeling Commands

    def set_node_prop(self):
        ...

    def set_block_prop(self):
        ...

    # Problem Commands

    # Mesh Commands

    # Editing Commands

    # Zoom Commands

    def zoom_natural(self):
        """Zooms to a “natural” view with sensible extents."""

        self._call_femm('zoomnatural', add_doctype_prefix=True)

    def zoom_out(self):
        """Zoom out by a factor of 50%."""

        self._call_femm('zoomout', add_doctype_prefix=True)

    def zoom_in(self):
        """Zoom in by a factor of 200%."""

        self._call_femm('zoomin', add_doctype_prefix=True)

    def zoom(self, x1, y1, x2, y2):
        """Set the display area to be from the bottom left corner specified by
        (x1, y1) to the top right corner specified by (x2, y2)."""

        self._call_femm_with_args('zoom', x1, y1, x2, y2)

    # View Commands

    # Object Properties

    # Miscellaneous


class PostProcessorAPI(BaseAPI):
    """Postprocessor API"""

    mode_prefix = 'o'

    def line_integral(self, integral_type):
        """Calculate the line integral for the defined contour. Returns typically two (possibly
        complex) values as results. For force and torque results, the 2× results are only relevant
        for problems where ω 6= 0. The 1× results are only relevant for incremental permeability
        AC problems. The 1× results represent the force and torque interactions between the
        steady-state and the incremental AC solution"""

        return self._call_femm_with_args('lineintegral', integral_type)

    def block_integral(self, integral_type):
        """Calculate a block integral for the selected blocks. This function returns one
        (possibly complex) value, e.g.: volume = mo_blockintegral(10)."""

        return self._call_femm_with_args('blockintegral', integral_type)

    def get_point_values(self, x, y):
        """Get the values associated with the point at x,y return values in order"""

        return self._call_femm_with_args('getpointvalues', x, y)
