
# Single source of truth for pixel index transforms (preview + export)

def linear_index(x, y, width):
    return y * width + x

def serpentine_index(x, y, width):
    if y % 2 == 0:
        return y * width + x
    else:
        return y * width + (width - 1 - x)

def get_index(x, y, width, height, serpentine=False):
    if serpentine:
        return serpentine_index(x, y, width)
    return linear_index(x, y, width)

def generate_index_map(width, height, serpentine=False):
    index_map = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(get_index(x, y, width, height, serpentine))
        index_map.append(row)
    return index_map
