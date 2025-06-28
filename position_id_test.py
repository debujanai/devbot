# Test script to debug position ID handling

def test_position_id_display():
    # Test different position ID values
    test_cases = [
        None,
        'N/A',
        0,
        12345,
        '12345'
    ]
    
    print("Testing position ID display:")
    for position_id in test_cases:
        # This is the code from bot.py
        position_id_display = f"`{position_id}`" if position_id and position_id != 'N/A' else "None"
        print(f"Position ID: {position_id}, Type: {type(position_id)}, Display: {position_id_display}")
        
        # Alternative implementation
        if position_id is not None and position_id != 'N/A' and position_id != 0:
            alt_display = f"`{position_id}`"
        else:
            alt_display = "None"
        print(f"  Alternative: {alt_display}")
    
    # Test the specific case from the user's report
    print("\nSpecific case test:")
    # The position ID might be 0 which evaluates to False in boolean context
    position_id = 0
    position_id_display = f"`{position_id}`" if position_id and position_id != 'N/A' else "None"
    print(f"Position ID: {position_id}, Display: {position_id_display}")
    
    # Fix for the issue
    position_id_display = f"`{position_id}`" if position_id is not None and position_id != 'N/A' else "None"
    print(f"Fixed Display: {position_id_display}")
    
    # Better fix that handles 0 correctly
    if position_id is not None and position_id != 'N/A':
        position_id_display = f"`{position_id}`"
    else:
        position_id_display = "None"
    print(f"Better Fixed Display: {position_id_display}")

if __name__ == "__main__":
    test_position_id_display() 