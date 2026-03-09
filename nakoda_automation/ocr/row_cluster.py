def cluster_rows(blocks, y_threshold=15):
    """
    blocks is a list of dicts: {"text": "...", "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], "conf": float}
    """
    if not blocks:
        return []
    
    # Extract y_min and x_min for clustering and sorting
    for b in blocks:
        b['y_min'] = min(point[1] for point in b['bbox'])
        b['x_min'] = min(point[0] for point in b['bbox'])
        
    # Sort vertically first
    blocks_sorted = sorted(blocks, key=lambda b: b['y_min'])
    
    rows = []
    current_row = [blocks_sorted[0]]
    current_y = blocks_sorted[0]['y_min']
    
    for b in blocks_sorted[1:]:
        if abs(b['y_min'] - current_y) <= y_threshold:
            current_row.append(b)
        else:
            rows.append(current_row)
            current_row = [b]
            current_y = b['y_min']
            
    if current_row:
        rows.append(current_row)
        
    structured_rows = []
    for row in rows:
        # Sort blocks in the row horizontally by x coordinate
        row_sorted = sorted(row, key=lambda b: b['x_min'])
        
        # Filter exclusions
        valid_blocks = []
        for b in row_sorted:
            # Ignore TOTAL and very short text
            if len(b['text']) < 3:
                continue
            if "TOTAL" in b['text'].upper():
                continue
            valid_blocks.append(b['text'])
            
        if valid_blocks:
            structured_rows.append(" ".join(valid_blocks))
            
    return structured_rows
