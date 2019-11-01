class AbstractImgEditor(object):
    def transform(self, img, preview=False):
        """
        Apply the transformation operation.

        Arguments:
            img -- image to transform
            preview -- indicates if we intend to use the result as a preview
                or as final result
        """
        assert()

    def transform_frame(self, img_size, frame):
        return frame

    def transform_point(self, img_size, point):
        return point

    def untransform_point(self, img_size, point):
        return point

    def __eq__(self, o):
        return type(self) == type(o)
