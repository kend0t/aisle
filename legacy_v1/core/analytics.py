import pandas as pd

def generate_reports(dwell_data, zone_names, fps, output_csv_path):
    print("\n" + "="*60)
    print(f"{'DWELL TIME & CUSTOMER JOURNEY SUMMARY':^60}")
    print("="*60)

    csv_data = []
    
    for track_id, data in dwell_data.items():
        # Make a copy of the completed journey
        journey = list(data["history"])
        
        # If the video ended while they were still in a zone, add that final chunk of time
        if data["current_zone"] is not None and data["frames"] > 0:
            journey.append({
                "zone": data["current_zone"],
                "seconds": round(data["frames"] / fps, 1)
            })
        
        # Only process people who actually entered at least one zone
        if len(journey) > 0:
            # Calculate the total seconds spent across all zones
            total_dwell = sum([step['seconds'] for step in journey])
            
            # Map the zone indices to their actual names (e.g., "Aisle 1")
            path_list = [zone_names[step['zone']] if step['zone'] < len(zone_names) else f"Zone {step['zone']}" for step in journey]
            path_str = " -> ".join(path_list)
            
            # Calculate the total time per individual zone
            time_per_zone = {}
            for step in journey:
                z_idx = step['zone']
                name = zone_names[z_idx] if z_idx < len(zone_names) else f"Zone {z_idx}"
                time_per_zone[name] = time_per_zone.get(name, 0) + step['seconds']
            
            # Print terminal summary for this specific customer
            print(f"\n[Customer ID: {track_id}]")
            print(f"  Full Path: {path_str}")
            print("  Path Breakdown:")
            for name, total_sec in time_per_zone.items():
                print(f"    - {name:<15} : {total_sec:>5.1f} seconds")
            
            # Build the core row dictionary for the CSV
            row_data = {
                "customer_id": track_id,
                "total_dwell": round(total_dwell, 1),
                "path": path_str
            }
            
            # Dynamically merge the individual zone times into the row
            row_data.update(time_per_zone)
            
            # Append the compiled data
            csv_data.append(row_data)

    # Print final footer to the terminal
    print("\n" + "="*60)
    print(f" Total Unique Persons Identified: {len(dwell_data)}")
    print("="*60)

    # Convert the list of dictionaries into a Pandas DataFrame and export
    if csv_data:
        system_df = pd.DataFrame(csv_data)
        
        # Replace all empty NaN values with 0 for zones the customer didn't visit
        system_df = system_df.fillna(0)
        
        # Export the DataFrame to a CSV file without the index column
        system_df.to_csv(output_csv_path, index=False)
        print(f"\nExported analytics successfully to {output_csv_path}")
        print(f"It contains {len(system_df)} rows with individual zone columns.")
    else:
        print("\nNo valid zone tracking data found. CSV export skipped.")