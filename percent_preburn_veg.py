##This file is intended to run as a notebook within ArcGISPro
##written for ArcGIS Pro v3.4

import re
import arcpy
from arcpy.sa import TabulateArea

arcpy.env.workspace = r"D:\Climate_Detrimental_Wildfire\CDW\CDW.gdb"

fire_fc = r"D:\Climate_Detrimental_Wildfire\CDW\CDW.gdb\all_fires_2001_2019_clip_single_burn_w_regions"
id_field = "Unique_ID"      
year_field = "FIREYEAR"    

raster_template = r"C:/Users/hrchapmandutton/Documents/ABoVE/ABoVE_{year}.tif" # Naming template
class_to_field_map = {
    1: "perEvrgrn",
    2: "perDecid",
    5: "perShrub",
    6: "perShrub",
    7: "perShrub",
    8: "perHerb",
    9: "perTusTund",
    11: "perFen",
    12: "perBog"    
}

years = list(range(2001, 2020)) #ends at 2019

results_dict = {} 
for year in years:
    if year <= 2014: 
        pre_burn_year = year - 1
    else:
        pre_burn_year = 2014

    raster_path = raster_template.format(year=pre_burn_year)

    if not arcpy.Exists(raster_path):
        print(f"Warning: Raster missing for year {pre_burn_year} ({raster_path}).")
    print(f"Processing fire year {year} with raster {pre_burn_year}...")

    # Select fire scars for the current year
    where_clause = f"{year_field} = '{year}'"
    fire_layer = "temp_fire_layer"
    arcpy.management.MakeFeatureLayer(fire_fc, fire_layer, where_clause)

    # Run Tabulate Area (calculates area of each veg value per fire scar)
    temp_table = "memory/tab_area_out"
    TabulateArea(fire_layer, id_field, raster_path, "VALUE", temp_table)

    # Identify value columns created by TabulateArea (e.g., VALUE_1, VALUE_2)
    fields = [f.name for f in arcpy.ListFields(temp_table)]
    val_cols = [f for f in fields if f.upper().startswith("VALUE")]

    # Map output table columns to raster class numbers
    col_map = {}
    for col in val_cols:
        digits = re.findall(r'\d+', col)
        if digits:
            col_map[col] = int(digits[-1])

    # Read area results and calculate percentages
    read_fields = [id_field] + list(col_map.keys())
    with arcpy.da.SearchCursor(temp_table, read_fields) as cursor:
        for row in cursor:
            oid = row[0]
            areas = row[1:]
            total_area = sum(areas)

            if total_area > 0:
                results_dict[oid] = {}
                for col_name, area in zip(col_map.keys(), areas):
                    class_val = col_map[col_name]
                    if class_val in class_to_field_map:
                        target_field = class_to_field_map[class_val]
                        results_dict[oid][target_field] = (area / total_area) * 100.0

    # Clean up temporary layers
    arcpy.management.Delete(fire_layer)
    arcpy.management.Delete(temp_table)

#Write calculated percentages back to feature class
target_fields = list(class_to_field_map.values())
update_fields = [id_field] + target_fields

with arcpy.da.UpdateCursor(fire_fc, update_fields) as cursor:
    for row in cursor:
        oid = row[0]
        if oid in results_dict:
            updated_row = [oid]
            for field in target_fields:
                # Assign calculated percentage or 0.0 if that veg type wasn't present in the scar
                updated_row.append(results_dict[oid].get(field, 0.0))
            cursor.updateRow(updated_row)

print("Successfully calculated pre-burn vegetation percentages!")
