import numpy as np
import rasterio
import shapely
from rasterio import features
from shapely.geometry import Polygon


def mask2poly(mask):
    all_polygons = []
    for shape, value in features.shapes(mask.astype(np.uint8), mask=(mask > 0),
                                        transform=rasterio.Affine(1.0, 0, 0, 0, 1.0, 0)):
        all_polygons.append(shapely.geometry.shape(shape))
    return all_polygons


def polygon2mask(polygons, shape):
    binary_mask = rasterio.features.rasterize(
        polygons,
        out_shape=shape
    )
    return (binary_mask*255).astype(np.uint8)


def eliminate_holes_and_tiny_objects(target_mask, width, height, eps=None, store_single=True, return_type='polygon',
                                     debug=False):
    assert return_type in ['polygon', 'mask', 'coordinates'], 'Specify correct return type.'
    all_polygons = mask2poly(mask=target_mask)
    if all_polygons != []:
        areas = [polygon.area for polygon in all_polygons]
        if store_single:
            all_polygons = all_polygons[areas.index(max(areas))]
        else:
            max_area = max(areas)
            all_polygons = [all_polygons[idx] for idx, area in enumerate(areas) if area/max_area > 0.005]
    else:
        return

    new_polygons = []
    for polygon in all_polygons:
        if polygon.area < 1000:
            continue
        list_interiors = []
        if eps is not None:
            for interior in polygon.interiors:
                p = Polygon(interior)
                if p.area > eps:
                    list_interiors.append(interior)
        new_polygon = Polygon(polygon.exterior.coords, holes=list_interiors)
        new_polygons.append(new_polygon)

    if return_type == 'coordinates':
        result = []
        for new_polygon in new_polygons:
            x, y = new_polygon.exterior.xy
            coordinates = np.vstack([np.array(x.tolist()), np.array(y.tolist())]).transpose().astype(int)
            result.append(coordinates)
    elif return_type == 'polygon':
        result = new_polygons
    else:
        result = (rasterio.features.rasterize(
            new_polygons,
            out_shape=(height, width)
        ) * 255).astype(np.uint8)

    return result
