import numpy as np
import cv2
from shapely.geometry import Polygon

from src.utils.draft.contour_refiner.geometry.polygon import MyPolygon
from cascade_psp.src.dev.utils.utils import search_anomaly_refined, search_anomaly_refined_v2  # , search_anomaly_refined_v3
from cascade_psp.src.dev.utils.utils_v1 import search_anomaly_refined_v3
from src.threshold_filter_cotourer.utils import vis_image, get_image, get_annotation
from src.threshold_filter_cotourer.utils import eliminate_holes_and_tiny_objects, vis_contours


def unsharp_mask(image, kernel_size=(5, 5), sigma=1.0, amount=1.0, threshold=0):
    """Return a sharpened version of the image, using an unsharp mask."""
    blurred = cv2.GaussianBlur(image, kernel_size, sigma)
    sharpened = float(amount + 1) * image - float(amount) * blurred
    sharpened = np.maximum(sharpened, np.zeros(sharpened.shape))
    sharpened = np.minimum(sharpened, 255 * np.ones(sharpened.shape))
    sharpened = sharpened.round().astype(np.uint8)
    if threshold > 0:
        low_contrast_mask = np.absolute(image - blurred) < threshold
        np.copyto(sharpened, image.astype(sharpened.dtype), where=low_contrast_mask)
    return sharpened


def get_object_contour(img_crop, return_type='mask', blur_mode='gaussian_blur', ksize=(7, 7), debug=False):
    assert blur_mode in ['simple_blur', 'gaussian_blur', 'no_blur']
    height, width = img_crop.shape
    if blur_mode == 'simple_blur':
        image = cv2.blur(img_crop, ksize)
    elif blur_mode == 'gaussian_blur':
        image = cv2.GaussianBlur(img_crop, ksize, 0)
    else:
        image = img_crop

    ret, thresh = cv2.threshold(image,  # .astype(np.uint8),
                                40,  # point_2,
                                255,
                                cv2.THRESH_BINARY_INV)  # | cv2.THRESH_OTSU
    cleared_mask = np.array(
        eliminate_holes_and_tiny_objects(thresh, width, height, eps=None, return_type=return_type))

    if debug:
        vis_image(cleared_mask)
        vis_contours(img_crop, cleared_mask)
    return cleared_mask


def crop_image_by_bb_coordinates(img_crop, full_size_minimals, pad=50, return_type='polygon', debug=False):
    # return_type = 'polygon'  # binary_mask  polygon
    height, width = img_crop.shape
    x_min, y_min = full_size_minimals
    refined_mask = get_object_contour(img_crop, blur_mode='gaussian_blur', ksize=(7, 7))
    refined_wo_holes = eliminate_holes_and_tiny_objects(refined_mask, width, height,
                                                        eps=None, return_type=return_type)
    if debug:
        if return_type == 'polygon':
            vis_contours(img_crop, refined_wo_holes)
        elif return_type == 'mask':
            vis_image(refined_wo_holes, True)
        else:
            raise NotImplemented

    if return_type == 'polygon':
        detected_object_polygons = []
        for polygon in refined_wo_holes:
            local_polygon = polygon.copy()
            local_polygon[:, 0] += x_min
            local_polygon[:, 1] += y_min - pad
            detected_object_polygons.append(local_polygon)
        return detected_object_polygons
    else:
        raise NotImplemented


def get_data(file_name, old_version=False, debug=False):
    npz_path = f'./examples/input/{file_name}.npz'
    img_raw = get_image(npz_path, old_version)
    init_beam = np.max(img_raw)
    json_path = f'./examples/output/{file_name}.json'
    annotations = get_annotation(json_path)
    if debug:
        vis_image(img_raw)
    return img_raw, annotations, init_beam


def substract_intersected_polygons(world_coordinate_polygons):
    poly_objects = [MyPolygon(world_coordinate_polygon) for world_coordinate_polygon in world_coordinate_polygons]
    num_polygons = len(poly_objects)
    for i_idx in range(num_polygons):
        for j_idx in range(num_polygons):
            if i_idx > j_idx:
                intersected_poly = poly_objects[i_idx].intersect_with(poly_objects[j_idx])
                if intersected_poly is not None:
                    if poly_objects[i_idx].get_area() > poly_objects[j_idx].get_area():
                        poly_objects[i_idx] = poly_objects[i_idx].sub(poly_objects[j_idx])
                    else:
                        poly_objects[j_idx] = poly_objects[j_idx].sub(poly_objects[i_idx])
    return poly_objects


def get_np_points_from_Polygon(polygon):
    x, y = polygon.exterior.xy
    np_poly = np.expand_dims(
        np.vstack(
            [
                np.array(x.tolist()),
                np.array(y.tolist())
            ]
        ).transpose(), axis=0
    ).astype(int)
    return np_poly


def refine_polygons(image, polygons, debug=False, version=3):
    # for idx, polygon in enumerate([Polygon(polygons[0])]):
    if not isinstance(polygons, list):
        polygons = [polygons]
    res_poly_list = []
    for idx, polygon_ in enumerate(polygons):
        if isinstance(polygon_, np.ndarray) or isinstance(polygon_, list):
            polygon = Polygon(polygon_)
        else:
            try:
                coordinates = polygon_.get_coordinates()
            except:
                coordinates = get_np_points_from_Polygon(polygon_)
            polygon = Polygon(coordinates)

        if polygon.area < 1000:
            continue

        poly = get_np_points_from_Polygon(polygon)
        if version == 1:
            poly = search_anomaly_refined(image, poly, debug=debug)
        elif version == 2:
            poly = search_anomaly_refined_v2(image, poly, debug=debug)
        elif version == 3:
            poly = search_anomaly_refined_v3(image, poly, debug=debug)
        else:
            raise NotImplemented

        res_poly_list.extend(poly)
    return res_poly_list


def main(debug=False):
    # 20210331STM0104727 20210512STM0106906  20211011STM0070035 202101170005780013 202101280015070037
    name = '202101280015070037'
    pad = 50
    old_version = False
    debug = False
    world_coordinate_polygons = []
    box_coordinates = []

    img_raw, annotations, init_beam = get_data(file_name=name, old_version=old_version, debug=debug)
    ####################################################################################################################
    # unsharped_image1 = unsharp_mask(img_raw, kernel_size=(3, 3), sigma=1.0, amount=1.0, threshold=0)
    # Image.fromarray(unsharped_image1).show()
    # unsharped_image6 = unsharp_mask(img_raw, kernel_size=(3, 3), sigma=6.0, amount=6.0, threshold=50)
    # Image.fromarray(unsharped_image6).show()
    # b, c = 0.5, 9
    # kernel = np.array([[-b, -b, -b],
    #                    [-b,  c, -b],
    #                    [-b, -b, -b]])
    # sharpened = cv2.filter2D(img_raw, -1, kernel)
    # Image.fromarray(sharpened).show()
    #
    # smoothed = cv2.GaussianBlur(img_raw, (9, 9), 10)
    # unsharped = cv2.addWeighted(img_raw, 1.5, smoothed, -0.5, 0)
    # Image.fromarray(unsharped).show()
    ####################################################################################################################

    prepared_images, prepared_polygons = [], []
    for object_ in annotations['prediction']:
        box_coordinates.append(object_['coord'])
        x_min, y_min, x_max, y_max = object_['coord']
        img_crop = img_raw[max(0, y_min - pad):y_max, x_min:x_max]
        img_crop = img_crop - img_crop.mean()
        polygon = crop_image_by_bb_coordinates(img_crop, [x_min, y_min], pad=50, debug=False)
        prepared_images.append(img_raw)
        prepared_polygons.append(polygon)

    poly_objects = substract_intersected_polygons([i[0] for i in prepared_polygons])

    for idx, (img_raw, polygon) in enumerate(zip(prepared_images, poly_objects)):  # prepared_polygons
        # if idx < 2:
        #     continue
        # vis_contours(img_raw, [polygon.get_coordinates()])
        world_coordinate_polygons.extend(refine_polygons(img_raw, polygon, debug=False))

    poly_objects = substract_intersected_polygons(world_coordinate_polygons)
    vis_contours(img_raw, [f.get_coordinates() for f in poly_objects], save_path=None)
    # for f in poly_objects:
    #     vis_contours(img_raw, [f.get_coordinates()])
    print('Done.')


if __name__ == '__main__':
    main(debug=False)
