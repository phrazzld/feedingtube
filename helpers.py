# strip a string of non-alphanumeric characters
def stripped(s):
    return ''.join(e for e in s if e.isalnum())

# format image filename properly
def name_image_file(image_id, title):
    name = image_id + stripped(title)
    name = '.'.join([name[:100], 'jpg'])
    name = name.encode('utf-8', 'ignore').decode('utf-8')
    return name

def build_flash_message(email):
    msg = "Sometimes this part takes a while."
    msg += "We'll send it over to {0} as soon as it's ready.".format(email)
    msg += "Thank you for your patience!"
    return msg
