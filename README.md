# DJ-MKV

DJ-MKV is a WIP, and some features that aren't supported yet are talked about. See the roadmap for the currently working features.

DJ-MKV is a disc archival and documenting system. It can read and save all of the metadata and content off of a disc. This metadata and content can then be archived for future generations. It is also designed to make library management and updating easier; an end goal is to allow old content to be re-read in the future and re-converted following newer standards. For example, in 2025 a disc may be read and transcoded to AVC (h.265) because that is the most compatible codec. Then, in 2030 the default codec is changed AV1 as in the future it (hypothetically) becomes more compatible. Older discs could be re-inserted in 2030 and automatically re-converted to the newer format.

Like Automatic Ripping Machine (arm), DJ-MKV uses MakeMKV to read and convert discs. Unlike ARM however, DJ-MKV focuses on documenting everything about the discs to make the content searchable. DJ-MKV is also built as many different, independent components. Metadata and content reading can be done by one computer, while transcoding can be handled by a separate computer. This is particularly useful for transcoding, where a small cluster of machines can be used to split the work.

## System Structure

### Reader

The reader service is used to read the metadata and content off of discs. It uses MakeMKV (along with a couple of custom IOCTL things) to interact with the disc and read all of the data off of it.

Metadata is copied into a database. It is stored in three tables: `discs`, `disc_titles`, and `disc_streams`.

### Converter

Converter is planned, but not implemented yet.

## Roadmap

The rough roadmap of the project is as follows:

 - [x] Basic disc metadata reading 
   - Disc metadata can be read and processed
 - [x] Basic disc database structure
   - A DB with a useful structure is available
 - [x] Read disc metadata into DB
   - The disc metadata can be read and saved into the DB automatically
 - [x] MQTT status messages while reading metadata
   - Status messages are sent during reading to allow other systems to display progress
 - [ ] Automatic content reading
   - Disc content is saved to the hard drive
 - [ ] MQTT status messages while reading content
   - Status messages are sent during reading to allow other systems to display progress
 - [ ] Automatic content conversion
   - Content is converted after being read for long term storage.
 - [ ] Web frontend
   - Add a web frontend to add/edit metadata to discs