import numpy as np
import supervision as sv

def get_store_zones():
    aisle_1 = np.array([[901, 386], [644, 699], [353, 581], [670, 330]])
    aisle_2 = np.array([[991, 404], [1206, 452], [1170, 715], [781, 719]])
    aisle_3 = np.array([[1142, 223], [1078, 420], [455, 284], [701, 145]])
    aisle_4 = np.array([[371, 332], [159, 266], [470, 101], [697, 145]])
    aisle_5 = np.array([[470, 97], [704, 27], [1271, 131], [1269, 243]])
    aisle_6 = np.array([[204, 81], [144, 288], [0, 244], [76, 67]])
    cashier = np.array([[3, 705], [1, 356], [168, 346], [114, 715]])

    polygons = [aisle_1, aisle_2, aisle_3, aisle_4, aisle_5, aisle_6, cashier]
    zone_names = ["Aisle 1", "Aisle 2", "Aisle 3", "Aisle 4", "Aisle 5", "Aisle 6", "Cashier"]

    zones = [
        sv.PolygonZone(polygon=poly, triggering_anchors=[sv.Position.BOTTOM_CENTER])
        for poly in polygons
    ]
    return zones, zone_names

