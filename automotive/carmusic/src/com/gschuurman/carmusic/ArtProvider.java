package com.gschuurman.carmusic;

import android.content.ContentProvider;
import android.content.ContentUris;
import android.content.ContentValues;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Binder;
import android.os.ParcelFileDescriptor;
import android.provider.MediaStore;
import android.util.Size;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;

/**
 * Album art for the car Media app: content://com.gschuurman.carmusic.art/album/<album id>. The
 * Media app has no access to this app's music, so the art is rendered here (MediaStore thumbnail
 * of the album) and cached as PNG.
 */
public final class ArtProvider extends ContentProvider {
    static final String AUTHORITY = "com.gschuurman.carmusic.art";
    private static final int SIZE_PX = 512;

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        final long albumId;
        try {
            albumId = Long.parseLong(uri.getLastPathSegment());
        } catch (NumberFormatException e) {
            throw new FileNotFoundException(uri.toString());
        }
        final File file = new File(getContext().getCacheDir(), "album_" + albumId + ".png");
        if (!file.exists()) {
            final Uri album = ContentUris.withAppendedId(
                    MediaStore.Audio.Albums.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), albumId);
            final long token = Binder.clearCallingIdentity();
            try {
                final Bitmap art = getContext().getContentResolver()
                        .loadThumbnail(album, new Size(SIZE_PX, SIZE_PX), null);
                final File tmp = new File(file.getPath() + ".tmp");
                try (FileOutputStream out = new FileOutputStream(tmp)) {
                    art.compress(Bitmap.CompressFormat.PNG, 100, out);
                }
                if (!tmp.renameTo(file)) throw new FileNotFoundException(uri.toString());
            } catch (IOException e) {
                // No embedded or folder art.
                throw new FileNotFoundException(uri.toString());
            } finally {
                Binder.restoreCallingIdentity(token);
            }
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public String getType(Uri uri) {
        return "image/png";
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] args) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] args) {
        return 0;
    }
}
